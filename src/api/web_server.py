"""
FastAPI Web Server for Riftech Security System
Provides REST API and WebSocket for real-time monitoring
"""

import asyncio
import base64
import io
import json
import logging
import time
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

import cv2
import numpy as np
import bcrypt
from jose import jwt
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    status,
    Request,
    Response,
    Header
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
    FileResponse
)
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from ..core.config import config
from ..core.logger import logger
from ..database.models import db

# Ensure data directory exists
Path("data").mkdir(parents=True, exist_ok=True)

# Security settings
SECRET_KEY = "riftech-security-secret-key-2024-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 hours

# Admin credentials (change in production!)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode('utf-8')

# WebSocket manager
class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if self.active_connections:
            message_json = json.dumps(message)
            for connection in self.active_connections.copy():
                try:
                    await connection.send_text(message_json)
                except:
                    self.disconnect(connection)
    
    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_text(json.dumps(message))
        except:
            self.disconnect(websocket)


manager = ConnectionManager()

# ========== MODELS ==========

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str


class ConfigUpdate(BaseModel):
    camera_type: Optional[str] = None
    rtsp_url: Optional[str] = None
    camera_id: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    detect_fps: Optional[int] = None
    yolo_confidence: Optional[float] = None
    yolo_model: Optional[str] = None
    face_tolerance: Optional[float] = None
    motion_threshold: Optional[int] = None
    motion_min_area: Optional[int] = None
    skeleton_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    default_mode: Optional[str] = None
    enable_gpu: Optional[bool] = None
    thread_count: Optional[int] = None
    log_level: Optional[str] = None


class ZoneCreate(BaseModel):
    points: List[List[int]] = Field(..., min_length=3)
    armed: bool = True
    name: Optional[str] = None


class ZoneUpdate(BaseModel):
    armed: Optional[bool] = None
    name: Optional[str] = None


class FaceUpload(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class ModeChange(BaseModel):
    mode: str = Field(..., pattern="^(normal|armed|alerted)$")


# ========== UTILITY FUNCTIONS ==========

def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )


async def get_current_user(authorization: str = Header(None)) -> str:
    """Get current user from token"""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    
    # Extract token from "Bearer <token>" format
    if authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
    else:
        token = authorization
    
    payload = verify_token(token)
    return payload.get("sub")


def encode_frame_to_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    """Encode numpy frame to JPEG bytes"""
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, encoded = cv2.imencode('.jpg', frame, encode_param)
    return encoded.tobytes()


# ========== FASTAPI APP ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    logger.info("Starting Riftech Security Web Server...")
    yield
    logger.info("Shutting down Riftech Security Web Server...")


app = FastAPI(
    title="Riftech Security System API",
    description="AI-Powered Security Camera System",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY
)

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Shared frame file path
SHARED_FRAME_PATH = Path("data/shared_frame.jpg")
SHARED_STATS_PATH = Path("data/shared_stats.json")


# ========== AUTHENTICATION ENDPOINTS ==========

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login and get access token"""
    if request.username != ADMIN_USERNAME:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    
    if not bcrypt.checkpw(
        request.password.encode('utf-8'),
        ADMIN_PASSWORD_HASH.encode('utf-8')
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    
    access_token = create_access_token(data={"sub": request.username})
    
    logger.info(f"User {request.username} logged in")
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        username=request.username
    )


@app.post("/api/auth/logout")
async def logout(current_user: str = Depends(get_current_user)):
    """Logout user"""
    logger.info(f"User {current_user} logged out")
    return {"message": "Successfully logged out"}


# ========== VIDEO STREAMING ==========

@app.get("/api/stream")
async def stream_video(
    bbox: bool = True,
    timestamp: bool = True,
    zones: bool = True,
    skeletons: bool = True,
    motion_boxes: bool = False,
    fps: int = 15,
    height: int = 720
):
    """
    Stream live video with AI detection overlay (MJPEG)
    
    Query Parameters:
        bbox: Show bounding boxes (default: True)
        timestamp: Show timestamp (default: True)
        zones: Show zones (default: True)
        skeletons: Show skeletons (default: True)
        motion_boxes: Show motion boxes (default: False)
        fps: Streaming FPS (default: 15)
        height: Frame height (default: 720)
    """
    
    # Try enhanced security system first
    try:
        from ..security_system_v2 import enhanced_security_system
        from ..core.frame_manager import frame_manager
        
        if enhanced_security_system.running:
            logger.info("Using enhanced security system for streaming (optimized)")
            
            async def generate():
                frame_count = 0
                last_fps_check = time.time()
                fps_counter = 0
                
                while True:
                    try:
                        # OPTIMIZATION: Read frame directly from shared memory
                        # Skip get_frame_with_overlays for performance
                        frame = frame_manager.read_frame("camera")
                        
                        if frame is None:
                            # Create error frame
                            frame = np.zeros((height, int(height * 16 / 9), 3), np.uint8)
                            cv2.putText(frame, "Connecting...", (10, height // 2),
                                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                        else:
                            # OPTIMIZATION: Only draw overlays if bbox=True
                            # For smooth streaming, minimal overhead
                            if bbox and frame_count % 3 == 0:  # Every 3rd frame
                                # Get tracked objects
                                tracked_objects = enhanced_security_system.tracking_worker.get_tracked_objects()
                                
                                # Draw minimal bounding boxes (no skeletons, no labels)
                                for obj in tracked_objects:
                                    if time.time() - obj.last_seen < 2.0:
                                        x1, y1, x2, y2 = obj.bbox
                                        color = (0, 255, 0) if obj.is_trusted else (0, 255, 255)
                                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            
                            # Draw timestamp if enabled (every frame)
                            if timestamp:
                                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                cv2.putText(frame, timestamp_str, (10, 30),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        
                        # OPTIMIZATION: Use faster resize and encode
                        width = int(height * frame.shape[1] / frame.shape[0])
                        frame = cv2.resize(frame, dsize=(width, height), 
                                         interpolation=cv2.INTER_LINEAR)
                        
                        # OPTIMIZATION: Lower quality for faster encoding
                        jpeg_bytes = encode_frame_to_jpeg(frame, quality=65)
                        
                        # Yield MJPEG frame
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n\r\n')
                        
                        # OPTIMIZATION: Calculate actual FPS
                        frame_count += 1
                        fps_counter += 1
                        current_time = time.time()
                        if current_time - last_fps_check >= 1.0:
                            actual_fps = fps_counter / (current_time - last_fps_check)
                            logger.debug(f"Stream FPS: {actual_fps:.1f}")
                            fps_counter = 0
                            last_fps_check = current_time
                        
                        # FPS control
                        await asyncio.sleep(1.0 / fps)
                        
                    except Exception as e:
                        logger.error(f"Error in streaming: {e}")
                        await asyncio.sleep(0.1)
            
            return StreamingResponse(
                generate(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )
    except ImportError:
        logger.info("Enhanced security system not available, using old system")
    
    # Fallback to old system
    async def generate():
        frame_count = 0
        while True:
            try:
                # Try to read shared frame from file
                if SHARED_FRAME_PATH.exists():
                    # Read frame stats to check if updated
                    if SHARED_STATS_PATH.exists():
                        stats_data = SHARED_STATS_PATH.read_text()
                        current_count = int(json.loads(stats_data).get("frame_count", 0))
                        
                        # Only read if frame is updated
                        if current_count > frame_count:
                            frame_count = current_count
                            
                            # Read and send frame
                            jpeg_bytes = SHARED_FRAME_PATH.read_bytes()
                            
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
                
                # Fallback: try security_system if available
                elif security_system and security_system.current_frame is not None:
                    frame = security_system.current_frame.copy()
                    jpeg_bytes = encode_frame_to_jpeg(frame)
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
                
                await asyncio.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                logger.error(f"Error streaming video: {e}")
                await asyncio.sleep(0.1)
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/frame.jpg")
async def get_latest_frame(
    bbox: bool = True,
    timestamp: bool = True,
    zones: bool = True,
    skeletons: bool = True,
    height: int = 720
):
    """
    Get latest frame with AI detection overlay (single image)
    
    Query Parameters:
        bbox: Show bounding boxes (default: True)
        timestamp: Show timestamp (default: True)
        zones: Show zones (default: True)
        skeletons: Show skeletons (default: True)
        height: Frame height (default: 720)
    """
    # Try enhanced security system first
    try:
        from ..security_system_v2 import enhanced_security_system
        
        if enhanced_security_system.running:
            draw_options = {
                "bounding_boxes": bbox,
                "timestamp": timestamp,
                "zones": zones,
                "motion_boxes": False,
                "skeletons": skeletons
            }
            
            frame = enhanced_security_system.get_frame_with_overlays("camera", draw_options)
            
            if frame is None:
                raise HTTPException(
                    status_code=503,
                    detail="Frame not available"
                )
            
            # Resize to requested height
            width = int(height * frame.shape[1] / frame.shape[0])
            frame = cv2.resize(frame, dsize=(width, height), interpolation=cv2.INTER_AREA)
            
            # Encode to JPEG
            jpeg_bytes = encode_frame_to_jpeg(frame, quality=85)
            
            return Response(
                content=jpeg_bytes,
                media_type="image/jpeg",
                headers={"Cache-Control": "no-store"}
            )
    except ImportError:
        pass
    
    # Fallback to old system
    if security_system and security_system.current_frame is not None:
        frame = security_system.current_frame.copy()
        
        # Resize to requested height
        width = int(height * frame.shape[1] / frame.shape[0])
        frame = cv2.resize(frame, dsize=(width, height), interpolation=cv2.INTER_AREA)
        
        # Encode to JPEG
        jpeg_bytes = encode_frame_to_jpeg(frame, quality=85)
        
        return Response(
            content=jpeg_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"}
        )
    
    raise HTTPException(
        status_code=503,
        detail="Frame not available"
    )


# ========== SYSTEM STATUS ENDPOINTS ==========

@app.get("/api/status")
async def get_status(current_user: str = Depends(get_current_user)):
    """Get system status"""
    if not security_system:
        raise HTTPException(
            status_code=503,
            detail="Security system not initialized"
        )
    
    status = security_system.get_system_status()
    return JSONResponse(content=status)


@app.get("/api/stats")
async def get_stats(current_user: str = Depends(get_current_user)):
    """Get system statistics"""
    
    # Try to read from shared file first
    if SHARED_STATS_PATH.exists():
        try:
            stats_data = json.loads(SHARED_STATS_PATH.read_text())
            return JSONResponse(content=stats_data)
        except Exception as e:
            logger.error(f"Error reading shared stats: {e}")
    
    # Fallback to security_system
    if security_system:
        stats = security_system.get_stats()
        return JSONResponse(content=stats)
    
    # Return default stats
    return JSONResponse(content={
        "fps": 0,
        "persons": 0,
        "trusted": 0,
        "unknown": 0,
        "breaches": 0
    })


@app.post("/api/mode", response_model=dict)
async def set_mode(
    mode_request: ModeChange,
    current_user: str = Depends(get_current_user)
):
    """Change system mode"""
    if not security_system:
        raise HTTPException(
            status_code=503,
            detail="Security system not initialized"
        )
    
    security_system.set_mode(mode_request.mode)
    
    logger.info(f"User {current_user} changed mode to {mode_request.mode}")
    
    # Broadcast to WebSocket clients
    await manager.broadcast({
        "type": "mode_change",
        "mode": mode_request.mode,
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "message": f"Mode changed to {mode_request.mode}",
        "mode": mode_request.mode
    }


# ========== CONFIGURATION ENDPOINTS ==========

@app.get("/api/config")
async def get_config(current_user: str = Depends(get_current_user)):
    """Get current configuration"""
    config_dict = {
        "camera": {
            "type": config.camera.type,
            "rtsp_url": config.camera.rtsp_url,
            "camera_id": config.camera.camera_id,
            "width": config.camera.width,
            "height": config.camera.height,
            "fps": config.camera.fps,
            "detect_fps": config.camera.detect_fps
        },
        "detection": {
            "yolo_confidence": config.detection.yolo_confidence,
            "yolo_model": config.detection.yolo_model,
            "face_tolerance": config.detection.face_tolerance,
            "motion_threshold": config.detection.motion_threshold,
            "motion_min_area": config.detection.motion_min_area,
            "skeleton_enabled": config.detection.skeleton_enabled
        },
        "alerts": {
            "telegram_enabled": config.alerts.telegram_enabled,
            "telegram_bot_token": config.alerts.telegram_bot_token,
            "telegram_chat_id": config.alerts.telegram_chat_id,
            "cooldown_seconds": config.alerts.cooldown_seconds,
            "snapshot_on_alert": config.alerts.snapshot_on_alert
        },
        "system": {
            "default_mode": config.system.default_mode,
            "enable_gpu": config.system.enable_gpu,
            "thread_count": config.system.thread_count
        }
    }
    return JSONResponse(content=config_dict)


@app.post("/api/config")
async def update_config(
    config_update: ConfigUpdate,
    current_user: str = Depends(get_current_user)
):
    """Update configuration"""
    # Update camera settings
    if config_update.camera_type:
        config.camera.type = config_update.camera_type
    if config_update.rtsp_url:
        config.camera.rtsp_url = config_update.rtsp_url
    if config_update.camera_id is not None:
        config.camera.camera_id = config_update.camera_id
    if config_update.width:
        config.camera.width = config_update.width
    if config_update.height:
        config.camera.height = config_update.height
    if config_update.fps:
        config.camera.fps = config_update.fps
    if config_update.detect_fps:
        config.camera.detect_fps = config_update.detect_fps
    
    # Update detection settings
    if config_update.yolo_confidence:
        config.detection.yolo_confidence = config_update.yolo_confidence
    if config_update.yolo_model:
        config.detection.yolo_model = config_update.yolo_model
    if config_update.face_tolerance:
        config.detection.face_tolerance = config_update.face_tolerance
    if config_update.motion_threshold:
        config.detection.motion_threshold = config_update.motion_threshold
    if config_update.motion_min_area:
        config.detection.motion_min_area = config_update.motion_min_area
    if config_update.skeleton_enabled is not None:
        config.detection.skeleton_enabled = config_update.skeleton_enabled
    
    # Update alert settings
    if config_update.telegram_enabled is not None:
        config.alerts.telegram_enabled = config_update.telegram_enabled
    if config_update.telegram_bot_token:
        config.alerts.telegram_bot_token = config_update.telegram_bot_token
    if config_update.telegram_chat_id:
        config.alerts.telegram_chat_id = config_update.telegram_chat_id
    
    # Update system settings
    if config_update.default_mode:
        config.system.default_mode = config_update.default_mode
    if config_update.enable_gpu is not None:
        config.system.enable_gpu = config_update.enable_gpu
    if config_update.thread_count:
        config.system.thread_count = config_update.thread_count
    if config_update.log_level:
        config.logging.level = config_update.log_level
    
    # Save to file
    config.save()
    
    logger.info(f"Configuration updated by {current_user}")
    
    return {"message": "Configuration updated successfully"}


# ========== ZONE ENDPOINTS ==========

@app.get("/api/zones")
async def get_zones(current_user: str = Depends(get_current_user)):
    """Get all security zones"""
    if not security_system:
        raise HTTPException(
            status_code=503,
            detail="Security system not initialized"
        )
    
    zones = security_system.zone_manager.get_all_zones()
    return JSONResponse(content={"zones": zones})


@app.post("/api/zones")
async def create_zone(
    zone: ZoneCreate,
    current_user: str = Depends(get_current_user)
):
    """Create new security zone"""
    if not security_system:
        raise HTTPException(
            status_code=503,
            detail="Security system not initialized"
        )
    
    zone_id = security_system.zone_manager.add_zone(
        zone.points,
        zone.armed,
        zone.name
    )
    
    logger.info(f"Zone {zone_id} created by {current_user}")
    
    return {
        "message": "Zone created successfully",
        "zone_id": zone_id
    }


@app.put("/api/zones/{zone_id}")
async def update_zone(
    zone_id: int,
    zone_update: ZoneUpdate,
    current_user: str = Depends(get_current_user)
):
    """Update security zone"""
    if not security_system:
        raise HTTPException(
            status_code=503,
            detail="Security system not initialized"
        )
    
    security_system.zone_manager.update_zone(
        zone_id,
        armed=zone_update.armed,
        name=zone_update.name
    )
    
    logger.info(f"Zone {zone_id} updated by {current_user}")
    
    return {"message": "Zone updated successfully"}


@app.delete("/api/zones/{zone_id}")
async def delete_zone(
    zone_id: int,
    current_user: str = Depends(get_current_user)
):
    """Delete security zone"""
    if not security_system:
        raise HTTPException(
            status_code=503,
            detail="Security system not initialized"
        )
    
    security_system.zone_manager.delete_zone(zone_id)
    
    logger.info(f"Zone {zone_id} deleted by {current_user}")
    
    return {"message": "Zone deleted successfully"}


@app.delete("/api/zones")
async def clear_all_zones(current_user: str = Depends(get_current_user)):
    """Clear all zones"""
    if not security_system:
        raise HTTPException(
            status_code=503,
            detail="Security system not initialized"
        )
    
    security_system.zone_manager.clear_all_zones()
    
    logger.info(f"All zones cleared by {current_user}")
    
    return {"message": "All zones cleared"}


# ========== FACE ENDPOINTS ==========

@app.get("/api/faces")
async def get_faces(current_user: str = Depends(get_current_user)):
    """Get all trusted faces"""
    faces_dir = Path(config.paths.trusted_faces_dir)
    
    if not faces_dir.exists():
        return JSONResponse(content={"faces": []})
    
    faces = []
    for face_file in faces_dir.glob("*.jpg"):
        face_name = face_file.stem
        faces.append({
            "name": face_name,
            "filename": face_file.name,
            "path": str(face_file)
        })
    
    return JSONResponse(content={"faces": faces})


@app.post("/api/faces/upload")
async def upload_face(
    name: str,
    file: bytes = None,
    current_user: str = Depends(get_current_user)
):
    """Upload trusted face"""
    if not file:
        raise HTTPException(
            status_code=400,
            detail="No file uploaded"
        )
    
    # Validate file is image
    try:
        image = cv2.imdecode(np.frombuffer(file, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid image file"
            )
    except:
        raise HTTPException(
            status_code=400,
            detail="Invalid image file"
        )
    
    # Save face
    faces_dir = Path(config.paths.trusted_faces_dir)
    faces_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize filename
    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_'))
    face_path = faces_dir / f"{safe_name}.jpg"
    
    cv2.imwrite(str(face_path), image)
    
    logger.info(f"Face {safe_name} uploaded by {current_user}")
    
    return {
        "message": "Face uploaded successfully",
        "name": safe_name
    }


@app.delete("/api/faces/{face_name}")
async def delete_face(
    face_name: str,
    current_user: str = Depends(get_current_user)
):
    """Delete trusted face"""
    faces_dir = Path(config.paths.trusted_faces_dir)
    face_path = faces_dir / f"{face_name}.jpg"
    
    if not face_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Face not found"
        )
    
    face_path.unlink()
    
    logger.info(f"Face {face_name} deleted by {current_user}")
    
    return {"message": "Face deleted successfully"}


# ========== ALERT ENDPOINTS ==========

@app.get("/api/alerts")
async def get_alerts(
    limit: int = 50,
    current_user: str = Depends(get_current_user)
):
    """Get alert history"""
    alerts_dir = Path(config.paths.alerts_dir)
    
    if not alerts_dir.exists():
        return JSONResponse(content={"alerts": []})
    
    alerts = []
    for alert_file in sorted(alerts_dir.glob("*.jpg"), reverse=True)[:limit]:
        alert_name = alert_file.stem
        alerts.append({
            "filename": alert_file.name,
            "name": alert_name,
            "timestamp": alert_name.split('_')[-1] if '_' in alert_name else alert_name
        })
    
    return JSONResponse(content={"alerts": alerts})


@app.get("/api/alerts/{alert_name}")
async def get_alert_image(alert_name: str):
    """Get alert image"""
    alert_path = Path(config.paths.alerts_dir) / alert_name
    
    if not alert_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )
    
    return FileResponse(
        path=str(alert_path),
        media_type="image/jpeg"
    )


# ========== RECORDINGS ENDPOINTS ==========

@app.get("/api/recordings")
async def get_recordings(
    limit: int = 20,
    current_user: str = Depends(get_current_user)
):
    """Get video recordings"""
    recordings_dir = Path(config.paths.recordings_dir)
    
    if not recordings_dir.exists():
        return JSONResponse(content={"recordings": []})
    
    recordings = []
    for rec_file in sorted(recordings_dir.glob("*.mp4"), reverse=True)[:limit]:
        rec_name = rec_file.stem
        recordings.append({
            "filename": rec_file.name,
            "name": rec_name,
            "size": rec_file.stat().st_size,
            "modified": rec_file.stat().st_mtime
        })
    
    return JSONResponse(content={"recordings": recordings})


@app.get("/api/snapshots")
async def get_snapshots(
    limit: int = 20,
    current_user: str = Depends(get_current_user)
):
    """Get snapshots"""
    snapshots_dir = Path(config.paths.snapshots_dir)
    
    if not snapshots_dir.exists():
        return JSONResponse(content={"snapshots": []})
    
    snapshots = []
    for snap_file in sorted(snapshots_dir.glob("*.jpg"), reverse=True)[:limit]:
        snap_name = snap_file.stem
        snapshots.append({
            "filename": snap_file.name,
            "name": snap_name,
            "size": snap_file.stat().st_size,
            "modified": snap_file.stat().st_mtime
        })
    
    return JSONResponse(content={"snapshots": snapshots})


# ========== WEBSOCKET ENDPOINT ==========

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            
            # Handle client messages if needed
            if data:
                message = json.loads(data)
                logger.info(f"Received WebSocket message: {message}")
                
                # Echo back or handle specific commands
                await websocket.send_text(json.dumps({
                    "type": "echo",
                    "message": "Message received"
                }))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ========== HTML PAGES ==========

@app.get("/", response_class=HTMLResponse)
async def read_login():
    """Serve login page"""
    login_path = Path("web/login.html")
    if login_path.exists():
        return HTMLResponse(content=login_path.read_text())
    return HTMLResponse(content="<h1>Login page not found</h1>")


@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard():
    """Serve dashboard page"""
    dashboard_path = Path("web/index.html")
    if dashboard_path.exists():
        return HTMLResponse(content=dashboard_path.read_text())
    return HTMLResponse(content="<h1>Dashboard not found</h1>")


# ========== HELPER FUNCTIONS ==========

async def broadcast_detection_update():
    """Broadcast detection updates to all WebSocket clients"""
    if not security_system:
        return
    
    stats = security_system.get_stats()
    await manager.broadcast({
        "type": "detection_update",
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    })


async def broadcast_alert(alert_type: str, message: str, photo_path: str = None):
    """Broadcast alert to all WebSocket clients"""
    await manager.broadcast({
        "type": "alert",
        "alert_type": alert_type,
        "message": message,
        "photo": photo_path,
        "timestamp": datetime.now().isoformat()
    })


# ========== START SERVER ==========

async def start_web_server(port: int = 8000):
    """Start FastAPI web server"""
    import uvicorn
    
    config_host = "0.0.0.0"
    
    logger.info(f"Starting web server on {config_host}:{port}")
    
    config_instance = uvicorn.Config(
        app=app,
        host=config_host,
        port=port,
        log_level="info"
    )
    
    server = uvicorn.Server(config_instance)
    await server.serve()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
