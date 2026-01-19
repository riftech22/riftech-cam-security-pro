"""
Configuration Management Module
Handles all application settings with YAML configuration
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
import yaml
import logging

# Setup basic logging for config loading
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directory for the application
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def get_data_dir() -> Path:
    """Get data directory dynamically"""
    return BASE_DIR / "data"


@dataclass
class CameraConfig:
    """Camera configuration settings"""
    type: str = "v380_split"  # rtsp, usb, or v380_split
    rtsp_url: str = "rtsp://admin:password@192.168.1.100:554/stream1"
    camera_id: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 15
    
    # V380 split camera settings
    split_enabled: bool = True
    detect_fps: int = 5  # Target FPS for V380 detection


@dataclass
class DetectionConfig:
    """AI detection configuration"""
    yolo_confidence: float = 0.20
    yolo_model: str = "yolov8n.pt"
    face_tolerance: float = 0.6
    motion_threshold: int = 15
    motion_min_area: int = 500
    skeleton_enabled: bool = True
    fixed_images_dir: str = "data/fixed_images"  # Keep for face detector


@dataclass
class PathsConfig:
    """File paths configuration - dynamically constructed"""
    base_dir: Optional[str] = None  # Can be overridden by config.yaml
    _internal_base_dir: str = "data"  # Default if not specified
    
    def __post_init__(self):
        """Post-initialization to handle base_dir"""
        if self.base_dir is None:
            # Use dynamic data dir if base_dir not specified
            self._data_dir = get_data_dir()
        else:
            # Use specified base_dir from config.yaml
            self._data_dir = Path(self.base_dir)
    
    @property
    def base_dir_path(self) -> Path:
        """Get base directory (compatibility)"""
        return self._data_dir
    @property
    def base_dir(self) -> Path:
        """Get base directory - handles both config.yaml and dynamic paths"""
        return self._data_dir
    
    @property
    def recordings_dir(self) -> Path:
        """Get recordings directory dynamically"""
        return self.base_dir / "recordings"
    
    @property
    def alerts_dir(self) -> Path:
        """Get alerts directory dynamically"""
        return self.base_dir / "alerts"
    
    @property
    def snapshots_dir(self) -> Path:
        """Get snapshots directory dynamically"""
        return self.base_dir / "snapshots"
    
    @property
    def logs_dir(self) -> Path:
        """Get logs directory dynamically"""
        return self.base_dir / "logs"
    
    @property
    def trusted_faces_dir(self) -> Path:
        """Get trusted faces directory dynamically"""
        return self.base_dir / "trusted_faces"
    
    @property
    def fixed_images_dir(self) -> Path:
        """Get fixed images directory dynamically"""
        return self.base_dir / "fixed_images"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "data/security_system.db"
    cleanup_days: int = 30


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_enabled: bool = True
    file_enabled: bool = True
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5


@dataclass
class AlertsConfig:
    """Alert configuration"""
    cooldown_seconds: int = 5
    snapshot_on_alert: bool = True
    recording_duration: int = 30
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    breach_mode: str = "normal"  # normal, armed, stealth


@dataclass
class SystemConfig:
    """System configuration"""
    default_mode: str = "normal"
    enable_gpu: bool = True
    thread_count: int = 4


class Config:
    """Main configuration class"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration from YAML file
        
        Args:
            config_path: Path to config file. If None, uses default config/config.yaml
        """
        # Set default config path
        if config_path is None:
            # Try to find config.yaml in several locations
            possible_paths = [
                "config/config.yaml",
                "config.yaml",
                "/home/riftech/project/riftech-cam-security-pro/config/config.yaml"
            ]
            
            for path in possible_paths:
                if Path(path).exists():
                    config_path = path
                    break
            
            if config_path is None:
                logger.warning("No config file found, using defaults")
                config_path = "config/config.yaml"  # Will use defaults
        
        self.config_path = config_path
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            # Try to load from file
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                # Load sections
                self.camera = CameraConfig(**config_data.get('camera', {}))
                self.detection = DetectionConfig(**config_data.get('detection', {}))
                self.paths = PathsConfig(**config_data.get('paths', {}))
                self.database = DatabaseConfig(**config_data.get('database', {}))
                self.logging = LoggingConfig(**config_data.get('logging', {}))
                self.alerts = AlertsConfig(**config_data.get('alerts', {}))
                self.system = SystemConfig(**config_data.get('system', {}))
                
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                # Use defaults
                self.camera = CameraConfig()
                self.detection = DetectionConfig()
                self.paths = PathsConfig()
                self.database = DatabaseConfig()
                self.logging = LoggingConfig()
                self.alerts = AlertsConfig()
                self.system = SystemConfig()
                
                logger.warning(f"Config file not found at {self.config_path}, using defaults")
            
            # Create directories
            self._create_directories()
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Use defaults on error
            self.camera = CameraConfig()
            self.detection = DetectionConfig()
            self.paths = PathsConfig()
            self.database = DatabaseConfig()
            self.logging = LoggingConfig()
            self.alerts = AlertsConfig()
            self.system = SystemConfig()
            self._create_directories()
    
    def _create_directories(self):
        """Create necessary directories"""
        directories = [
            self.paths.base_dir,
            self.paths.recordings_dir,
            self.paths.alerts_dir,
            self.paths.snapshots_dir,
            self.paths.logs_dir,
            self.paths.trusted_faces_dir,
            self.paths.fixed_images_dir
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def reload(self):
        """Reload configuration from file"""
        logger.info("Reloading configuration...")
        self._load_config()
        logger.info("Configuration reloaded")
    
    def save(self, config_path: Optional[str] = None):
        """Save current configuration to file
        
        Args:
            config_path: Path to save config. If None, uses current config_path
        """
        if config_path is None:
            config_path = self.config_path
        
        config_data = {
            'camera': self.camera.__dict__,
            'detection': self.detection.__dict__,
            'paths': self.paths.__dict__,
            'database': self.database.__dict__,
            'logging': self.logging.__dict__,
            'alerts': self.alerts.__dict__,
            'system': self.system.__dict__
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Configuration saved to {config_path}")


# Global config instance
config = Config()
