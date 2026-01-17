# Riftech Security System - Web Server

🎉 **Complete Web Interface with Cyber Neon Theme!**

## 📋 Overview

Modern, responsive web interface for Riftech Security System with:
- 🎨 Cyber neon hacker theme with animations
- 🔐 JWT authentication with bcrypt
- 📺 Live video streaming
- 🤖 AI detection real-time
- 📱 Fully responsive (mobile/desktop)
- 🌐 WebSocket support
- ⚡ FastAPI backend
- 🌍 Cloudflared tunnel support

## ✨ Features

### 🎨 Cyber Neon Theme
- Matrix rain background
- Scanlines effect
- Neon glow effects
- Glitch animations
- Smooth transitions
- Dark mode optimized

### 🔐 Authentication
- JWT token-based authentication
- Bcrypt password hashing
- Secure session management
- Auto-logout on token expiry

### 📺 Live Monitoring
- Real-time video streaming
- FPS display
- Resolution info
- Mode indicator
- Snapshot capture

### 🤖 AI Detection
- Real-time stats display
- Person detection count
- Trusted vs unknown faces
- Breach counter
- Live updates via WebSocket

### ⚙️ Configuration
- Camera settings (RTSP, USB, V380)
- Detection parameters (YOLO confidence, models)
- Face recognition settings
- Motion detection thresholds
- Telegram notifications
- System settings

### 🗺️ Zone Management
- Visual zone editor
- Click-to-create zones
- Multiple zones support
- Arm/Disarm zones
- Delete individual or all zones

### 👤 Face Management
- Upload trusted faces
- Delete faces
- Display face gallery
- Auto-detection integration

### 🚨 Alert System
- Alert history with images
- Real-time notifications
- Alert timestamps
- View full alert images
- Auto-refresh

## 📁 File Structure

```
riftech-cam-security-pro/
├── src/
│   └── api/
│       └── web_server.py          # FastAPI backend
├── web/
│   ├── index.html                 # Main dashboard
│   ├── login.html                 # Login page
│   └── static/
│       ├── css/
│       │   └── cyber-neon.css     # Cyber theme styles
│       └── js/
│           └── app.js            # Frontend JavaScript
├── start-web.sh                  # Start script
├── web-server.service            # Systemd service
├── CLOUDFLARED_SETUP.md          # Tunnel setup guide
└── requirements.txt              # Dependencies
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install web server dependencies
pip install fastapi uvicorn[standard] websockets python-jose[cryptography] passlib[bcrypt] pydantic python-multipart
```

Or use start script (auto-installs):

```bash
./start-web.sh
```

### 2. Start Web Server

```bash
./start-web.sh
```

Web interface will be available at:
- **Local:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### 3. Login

Default credentials:
- **Username:** `admin`
- **Password:** `admin`

⚠️ **IMPORTANT:** Change default password in production!

### 4. Access Dashboard

After login, you'll see:
- Live video stream
- Real-time stats
- Recent alerts
- Configuration options

## 📱 Mobile Access

### Method 1: Cloudflared Tunnel (Recommended)

See `CLOUDFLARED_SETUP.md` for complete setup.

Quick setup:

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
sudo mv cloudflared-linux-arm64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Login and create tunnel
cloudflared tunnel login
cloudflared tunnel create riftech-security
cloudflared tunnel route dns riftech-security security.yourdomain.com

# Create config file
nano cloudflared-config.yml
```

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /root/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: security.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

```bash
# Start tunnel
cloudflared tunnel --config cloudflared-config.yml run
```

Now access from anywhere:
```
https://security.yourdomain.com
```

### Method 2: Port Forwarding

1. Forward port 8000 on router to device IP
2. Access via public IP:
   ```
   http://YOUR_PUBLIC_IP:8000
   ```

### Method 3: Local Network

Access from devices on same network:
```
http://DEVICE_IP:8000
```

## ⚙️ Configuration

### Change Default Credentials

Edit `src/api/web_server.py`:

```python
# Find and change these lines
ADMIN_USERNAME = "your-username"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(b"your-secure-password", bcrypt.gensalt()).decode('utf-8')
```

Or generate hash:

```python
python3 -c "import bcrypt; print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode('utf-8'))"
```

### Change Secret Key

Edit `src/api/web_server.py`:

```python
# Generate random key
SECRET_KEY = "your-random-secret-key-here"
```

Generate key:

```python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Change Server Port

Edit `start-web.sh` or systemd service:

```bash
--port 8080  # Change to desired port
```

## 🔧 API Endpoints

### Authentication
- `POST /api/auth/login` - Login and get token
- `POST /api/auth/logout` - Logout

### System Status
- `GET /api/status` - Get system status
- `GET /api/stats` - Get detection stats
- `POST /api/mode` - Change system mode

### Configuration
- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration

### Zones
- `GET /api/zones` - Get all zones
- `POST /api/zones` - Create zone
- `PUT /api/zones/{id}` - Update zone
- `DELETE /api/zones/{id}` - Delete zone
- `DELETE /api/zones` - Clear all zones

### Faces
- `GET /api/faces` - Get all faces
- `POST /api/faces/upload` - Upload face
- `DELETE /api/faces/{name}` - Delete face

### Alerts
- `GET /api/alerts` - Get alert history
- `GET /api/alerts/{name}` - Get alert image

### Video Stream
- `GET /api/stream` - Live video stream

### WebSocket
- `WS /api/ws` - Real-time updates

## 🎨 Customization

### Change Theme Colors

Edit `web/static/css/cyber-neon.css`:

```css
:root {
    --neon-green: #00ff41;   /* Main accent color */
    --neon-cyan: #00ffff;     /* Secondary accent */
    --neon-pink: #ff00ff;     /* Tertiary accent */
    --bg-primary: #0a0a0f;    /* Main background */
}
```

### Modify Logo

Edit HTML files to change branding:

```html
<div class="navbar-brand">
    Your <span>Brand</span>
</div>
```

### Add Custom Pages

1. Create HTML file in `web/`
2. Add route in `src/api/web_server.py`:

```python
@app.get("/your-page", response_class=HTMLResponse)
async def your_page():
    page_path = Path("web/your-page.html")
    if page_path.exists():
        return HTMLResponse(content=page_path.read_text())
    return HTMLResponse(content="<h1>Page not found</h1>")
```

## 🔒 Security Best Practices

### 1. Use HTTPS
- Cloudflared provides automatic HTTPS
- Or use Let's Encrypt with reverse proxy

### 2. Strong Passwords
- Change default credentials
- Use minimum 12 characters
- Mix letters, numbers, symbols

### 3. Secret Key
- Generate random secret key
- Store securely
- Don't share

### 4. Network Security
- Use firewall (ufw)
- Restrict access if possible
- Monitor logs

### 5. Regular Updates
```bash
pip install --upgrade fastapi uvicorn websockets
```

## 🐛 Troubleshooting

### Web server won't start

```bash
# Check dependencies
pip list | grep -E "fastapi|uvicorn|websockets"

# Check port is not in use
lsof -i :8000
```

### Can't login

```bash
# Check server logs
tail -f logs/riftech-security.log

# Reset password if needed
# Edit src/api/web_server.py
```

### Video stream not working

```bash
# Check security system is running
ps aux | grep python

# Check camera connection
# Verify camera in config.yaml
```

### WebSocket disconnected

```bash
# Check if ws endpoint is reachable
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8000/api/ws
```

### Mobile not loading

1. Check internet connection
2. Verify tunnel is running
3. Check Cloudflare dashboard
4. Try different browser

## 📊 Monitoring

### View Logs

```bash
# Systemd logs
sudo journalctl -u riftech-web-server -f

# Application logs
tail -f logs/riftech-security.log
```

### Check Status

```bash
# Service status
sudo systemctl status riftech-web-server

# Process status
ps aux | grep uvicorn
```

### Performance

Monitor resources:
```bash
htop
```

## 🚀 Performance Tips

### 1. Reduce Video Quality

Edit `config/config.yaml`:

```yaml
camera:
  width: 640    # Lower resolution
  height: 480
  fps: 10       # Lower FPS
```

### 2. Optimize Detection

```yaml
detection:
  detect_fps: 2        # Reduce detection frequency
  yolo_model: yolov8n  # Use faster model
```

### 3. Enable Caching

Use browser caching for static assets:

```python
# Add to web_server.py
app.mount("/static", StaticFiles(directory="web/static"), name="static")
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [WebSocket MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Cloudflared Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)

## 🤝 Support

For issues or questions:
1. Check this README
2. Review `CLOUDFLARED_SETUP.md`
3. Check application logs
4. Create issue on GitHub

## 📝 License

See LICENSE file for details.

## 🎉 Enjoy!

Your Riftech Security System now has a modern, beautiful web interface! 🚀

Access from anywhere, monitor in real-time, and stay secure! 🔒
