# Changelog

All notable changes to the Riftech Security System project.

## [2.0.0] - 2024-01-17

### Added
- Complete modular architecture rewrite
- YAML-based configuration system in config/ directory
- Professional logging with file rotation
- Async database operations using aiosqlite
- 33-point skeleton tracking with MediaPipe
- Advanced motion detection with heatmaps
- Polygon-based security zones
- Trusted face recognition system
- Three system modes: Normal, Armed, Alerted
- Web interface with real-time statistics
- Systemd service support
- Comprehensive installation scripts
- Type hints throughout codebase
- Threaded processing for better performance
- GPU auto-detection and utilization
- Alert cooldown system
- FFmpeg pipeline for stable RTSP streaming

### Changed
- Moved configuration from .env to YAML files
- Restructured project with src/ directory
- Improved error handling and recovery
- Enhanced camera capture with better stability
- Optimized detection pipeline
- Better resource cleanup on shutdown
- Improved zone breach detection

### Fixed
- Camera connection issues with RTSP
- Memory leaks in detection loop
- Database lock issues with concurrent access
- Face recognition loading failures
- Log file growing indefinitely

### Removed
- Old monolithic architecture
- Environment variable-based configuration
- Synchronous database operations
- Basic logging system

## [1.0.0] - 2023-01-01

### Added
- Initial release
- Basic person detection with YOLO
- Simple alert system
- Web interface
- Zone management
- Face recognition
- Motion detection
