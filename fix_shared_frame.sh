#!/bin/bash

# Fix shared frame issue - Replace shared memory with file-based approach

echo "======================================"
echo "Fixing Shared Frame Issue"
echo "======================================"

# Step 1: Add SharedFrameWriter to CaptureWorker
echo "Step 1: Updating CaptureWorker in security_system_v2.py..."

# Add import
if ! grep -q "from .core.shared_frame import SharedFrameWriter" src/security_system_v2.py; then
    sed -i '/from .core.frame_manager import frame_manager/a\from .core.shared_frame import SharedFrameWriter' src/security_system_v2.py
fi

# Add shared_frame_writer to CaptureWorker __init__
if ! grep -q "self.shared_frame_writer" src/security_system_v2.py; then
    sed -i '/self.motion_interval = 5  # Only detect every N frames/a\        self.shared_frame_writer = None' src/security_system_v2.py
fi

# Initialize shared_frame_writer in EnhancedSecuritySystem.initialize()
if ! grep -q "shared_frame_writer = SharedFrameWriter" src/security_system_v2.py; then
    sed -i '/logger.warning("Frame already registered, attaching...")/a\
\
        # Initialize file-based shared frame (for web server)\
        frame_shape = (config.camera.height, config.camera.width, 3)\
        self.shared_frame_writer = SharedFrameWriter("camera", frame_shape)' src/security_system_v2.py
fi

# Add write to shared_frame_writer in CaptureWorker
if ! grep -q "self.shared_frame_writer.write" src/security_system_v2.py; then
    sed -i '/frame_manager.write_frame(self.camera_name, full_frame)/a\
                # Also write to file-based shared frame (for web server)\
                if self.shared_frame_writer:\
                    self.shared_frame_writer.write(full_frame)' src/security_system_v2.py
fi

echo "✓ Step 1: CaptureWorker updated"

# Step 2: Update web_server.py to use SharedFrameReader
echo "Step 2: Updating web_server.py..."

# Add import
if ! grep -q "from ..core.shared_frame import SharedFrameReader" src/api/web_server.py; then
    sed -i '/from ..core.frame_manager import frame_manager/a\from ..core.shared_frame import SharedFrameReader' src/api/web_server.py
fi

# Initialize SharedFrameReader
if ! grep -q "shared_frame_reader" src/api/web_server.py; then
    sed -i '/logger.info("Using enhanced security system for streaming (optimized)")/a\
            shared_frame_reader = SharedFrameReader("camera")' src/api/web_server.py
fi

# Replace frame_manager.read_frame with shared_frame_reader.read
sed -i 's/frame = frame_manager.read_frame("camera")/frame = shared_frame_reader.read()/g' src/api/web_server.py

echo "✓ Step 2: Web server updated"

echo "======================================"
echo "Shared Frame Fix Complete!"
echo "======================================"

echo ""
echo "Changes made:"
echo "  ✓ security_system_v2.py - Added SharedFrameWriter"
echo "  ✓ web_server.py - Added SharedFrameReader"
echo "  ✓ Frame sharing now uses file-based approach"
echo ""
echo "Next steps:"
echo "  1. Restart services:"
echo "     sudo systemctl restart riftech-security-v2"
echo "     sudo systemctl restart riftech-web-server"
echo ""
echo "  2. Check logs:"
echo "     sudo journalctl -u riftech-web-server -f | grep Stream FPS"
echo ""
