# Cloudflared Setup for Riftech Security System

## 🌐 What is Cloudflared?

Cloudflared is a secure tunnel that allows you to expose your web server to the internet without:
- ❌ Router port forwarding
- ❌ Public IP address
- ❌ Firewall configuration
- ❌ DNS configuration

## ✨ Features

- ✅ HTTPS/SSL automatically
- ✅ Secure tunneling
- ✅ Works behind NAT
- ✅ No router configuration needed
- ✅ Fast connection
- ✅ WebSocket support
- ✅ Access from anywhere

## 📋 Prerequisites

- Cloudflare account (free tier)
- Ubuntu/Debian system
- Internet connection

## 🔧 Installation

### 1. Download and Install Cloudflared

```bash
# For Ubuntu/Debian (amd64)
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# For Raspberry Pi (arm64)
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
sudo mv cloudflared-linux-arm64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Verify installation
cloudflared --version
```

### 2. Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This will:
1. Open a browser window
2. Ask you to login to Cloudflare
3. Authorize the tunnel
4. Save authentication token

### 3. Create a Tunnel

```bash
# Create tunnel
cloudflared tunnel create riftech-security

# Note the tunnel ID (e.g., abc123-def456-ghi789)
# You'll need this later
```

### 4. Configure Tunnel

Create configuration file `cloudflared-config.yml`:

```yaml
tunnel: abc123-def456-ghi789  # Replace with your tunnel ID
credentials-file: /root/.cloudflared/abc123-def456-ghi789.json

ingress:
  - hostname: security.yourdomain.com  # Replace with your domain
    service: http://localhost:8000
  - service: http_status:404
```

**Important:** Replace:
- `abc123-def456-ghi789` with your actual tunnel ID
- `security.yourdomain.com` with your desired subdomain and domain

### 5. Route DNS

```bash
# Route DNS to tunnel
cloudflared tunnel route dns riftech-security security.yourdomain.com
```

This creates a DNS record pointing to your tunnel.

## 🚀 Running the Tunnel

### Method 1: Manual Start

```bash
# Start tunnel
cloudflared tunnel --config cloudflared-config.yml run
```

### Method 2: Auto-start with Web Server

Modify `start-web.sh` to start cloudflared automatically:

```bash
# Start web server in background
python3 -m uvicorn src.api.web_server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log &

# Start cloudflared tunnel
cloudflared tunnel --config cloudflared-config.yml run

# When stopping, kill both processes
trap 'pkill -f uvicorn; pkill -f cloudflared' EXIT
```

### Method 3: Systemd Service

Create systemd service file:

```bash
sudo nano /etc/systemd/system/riftech-web-server.service
```

Content:

```ini
[Unit]
Description=Riftech Security System - Web Server + Cloudflared Tunnel
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/riftech/project/riftech-cam-security-pro
Environment="PATH=/home/riftech/project/riftech-cam-security-pro/venv/bin"
ExecStart=/home/riftech/project/riftech-cam-security-pro/start-web-with-tunnel.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=riftech-web-server

[Install]
WantedBy=multi-user.target
```

Create `start-web-with-tunnel.sh`:

```bash
#!/bin/bash
set -e

# Activate virtual environment
source venv/bin/activate

# Start web server
python3 -m uvicorn src.api.web_server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log &

WEB_PID=$!

# Wait for web server to start
sleep 3

# Start cloudflared tunnel
cloudflared tunnel --config cloudflared-config.yml run

# Cleanup on exit
trap 'kill $WEB_PID' EXIT
```

Make it executable:

```bash
chmod +x start-web-with-tunnel.sh
chmod +x start-web.sh
```

Enable and start service:

```bash
sudo systemctl enable riftech-web-server
sudo systemctl start riftech-web-server
sudo systemctl status riftech-web-server
```

## 📱 Accessing from Mobile

Once cloudflared is running, you can access your security system from anywhere:

1. **Desktop:**
   ```
   https://security.yourdomain.com
   ```

2. **Mobile:**
   ```
   https://security.yourdomain.com
   ```
   Works on any mobile browser!

3. **API:**
   ```
   https://security.yourdomain.com/api/status
   https://security.yourdomain.com/api/stream
   ```

## 🔒 Security Considerations

### 1. Change Default Passwords

Edit `src/api/web_server.py`:

```python
# Change these in production!
ADMIN_USERNAME = "your-secure-username"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(b"your-secure-password", bcrypt.gensalt()).decode('utf-8')
```

### 2. Enable HTTPS

Cloudflared automatically provides HTTPS!

### 3. Use Strong Secret Key

Edit `src/api/web_server.py`:

```python
SECRET_KEY = "generate-a-very-long-random-string-here"
```

Generate random key:

```python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Cloudflare Access (Optional)

For additional security, enable Cloudflare Access:

1. Go to Cloudflare Zero Trust dashboard
2. Navigate to Access > Applications
3. Add application for your domain
4. Configure authentication (Email, Google, etc.)

## 📊 Monitoring

### View Tunnel Status

```bash
# Check if tunnel is running
ps aux | grep cloudflared

# View tunnel logs
journalctl -u riftech-web-server -f
```

### Cloudflare Dashboard

1. Go to Cloudflare Zero Trust dashboard
2. Navigate to Network > Tunnels
3. View your tunnel status, traffic, and logs

## 🐛 Troubleshooting

### Tunnel won't start

```bash
# Check logs
cloudflared tunnel --config cloudflared-config.yml run --loglevel debug

# Check credentials
ls -la ~/.cloudflared/
```

### Can't access from outside

1. Check if tunnel is running:
   ```bash
   ps aux | grep cloudflared
   ```

2. Check if web server is running:
   ```bash
   curl http://localhost:8000
   ```

3. Check Cloudflare dashboard for tunnel status

4. Check DNS records in Cloudflare

### DNS not resolving

1. Wait a few minutes (DNS propagation)
2. Check DNS records in Cloudflare dashboard
3. Verify tunnel is running
4. Check if `security.yourdomain.com` points to tunnel

### Slow connection

1. Check your internet connection
2. Try different Cloudflare edge locations
3. Check tunnel logs for errors

## 🔄 Updating Cloudflared

```bash
# Check for updates
cloudflared update

# Or manually download new version
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared
```

## 📝 Configuration Reference

Full `cloudflared-config.yml` options:

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /root/.cloudflared/YOUR_TUNNEL_ID.json

# Optional: Proxy protocol
proxy-addr: 127.0.0.1
proxy-port: 0
proxy-type: socks5

# Optional: Metrics
metrics: 127.0.0.1:2000
metrics-update-freq: 5s

# Optional: No-autoupdate
no-autoupdate: true

ingress:
  - hostname: security.yourdomain.com
    service: http://localhost:8000
  
  # Multiple domains
  - hostname: security2.yourdomain.com
    service: http://localhost:8001
  
  # Local service
  - hostname: internal.yourdomain.com
    service: http://localhost:3000
  
  # Final catch-all (required)
  - service: http_status:404
```

## 🎉 Success!

Your Riftech Security System is now accessible from anywhere in the world!

- 📱 Mobile access
- 🖥️ Desktop access
- 🔒 HTTPS/SSL
- 🚀 Fast connection
- 🌍 Global CDN

Enjoy monitoring your security system from anywhere! 🚀
