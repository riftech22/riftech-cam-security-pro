# Environment Variables Setup Guide
**Riftech Security System V2**

---

## 📋 Overview

Untuk keamanan maksimal, sistem ini menggunakan **environment variables** untuk mengatur sensitive data seperti:
- JWT Secret Key
- Admin Credentials
- Configuration options

---

## 🔐 Required Environment Variables

### 1. RIFTECH_SECRET_KEY (REQUIRED for Production)

**Purpose:** Secret key untuk JWT authentication tokens

**Generate Random Key:**
```bash
# Option 1: Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 2: Using OpenSSL
openssl rand -base64 32

# Option 3: Using Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

**Example:**
```bash
export RIFTECH_SECRET_KEY="k7xQ9Jm2Pv5Rn8Yt4Wq1Zd6Ac3Bf9Gh2Jm5Np8Qr1St"
```

---

### 2. RIFTECH_ADMIN_USERNAME (REQUIRED for Production)

**Purpose:** Username untuk login ke admin panel

**Example:**
```bash
export RIFTECH_ADMIN_USERNAME="riftech_admin"
```

---

### 3. RIFTECH_ADMIN_PASSWORD (REQUIRED for Production)

**Purpose:** Password untuk login ke admin panel

**Generate Strong Password:**
```bash
# Using Python
python -c "import secrets; import string; chars = string.ascii_letters + string.digits + string.punctuation; print(''.join(secrets.choice(chars) for _ in range(20)))"
```

**Example:**
```bash
export RIFTECH_ADMIN_PASSWORD="MyS3cur3P@ssw0rd!2024"
```

---

## 🚀 Setup Methods

### Method 1: Temporary (Session Only)

```bash
# Set variables for current session
export RIFTECH_SECRET_KEY="your-secret-key-here"
export RIFTECH_ADMIN_USERNAME="your-admin-username"
export RIFTECH_ADMIN_PASSWORD="your-strong-password"

# Verify
echo $RIFTECH_SECRET_KEY
echo $RIFTECH_ADMIN_USERNAME
echo $RIFTECH_ADMIN_PASSWORD

# Start services
python main_v2.py
```

**Note:** Variables will be lost when you close terminal.

---

### Method 2: Persistent (System-wide)

**For systemd services:**

1. Create environment file:
```bash
sudo nano /etc/riftech-security/environment
```

2. Add variables:
```bash
RIFTECH_SECRET_KEY=k7xQ9Jm2Pv5Rn8Yt4Wq1Zd6Ac3Bf9Gh2Jm5Np8Qr1St
RIFTECH_ADMIN_USERNAME=riftech_admin
RIFTECH_ADMIN_PASSWORD=MyS3cur3P@ssw0rd!2024
```

3. Set permissions (IMPORTANT!):
```bash
sudo chmod 600 /etc/riftech-security/environment
sudo chown root:root /etc/riftech-security/environment
```

4. Update systemd service file:
```bash
sudo nano /etc/systemd/system/riftech-security-v2.service
```

Add this line in `[Service]` section:
```ini
[Service]
EnvironmentFile=/etc/riftech-security/environment
...
```

5. Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart riftech-security-v2
```

---

### Method 3: User Profile (Permanent)

**For user-level persistence:**

1. Edit bash profile:
```bash
nano ~/.bashrc
```

2. Add at the end:
```bash
# Riftech Security System Environment Variables
export RIFTECH_SECRET_KEY="your-secret-key-here"
export RIFTECH_ADMIN_USERNAME="your-admin-username"
export RIFTECH_ADMIN_PASSWORD="your-strong-password"
```

3. Reload profile:
```bash
source ~/.bashrc
```

---

### Method 4: .env File (Development Only)

**For development/testing:**

1. Create `.env` file in project root:
```bash
cd ~/riftech-cam-security-pro
nano .env
```

2. Add variables:
```bash
RIFTECH_SECRET_KEY=your-secret-key-here
RIFTECH_ADMIN_USERNAME=your-admin-username
RIFTECH_ADMIN_PASSWORD=your-strong-password
```

3. Add to `.gitignore`:
```bash
echo ".env" >> .gitignore
```

4. Load in Python (update code):
```python
from dotenv import load_dotenv
load_dotenv()  # Load .env file
```

5. Install python-dotenv:
```bash
pip install python-dotenv
```

**⚠️ WARNING:** Never commit `.env` file to version control!

---

## 🔍 Verify Environment Variables

### Check if variables are set:

```bash
# Check individual variables
echo $RIFTECH_SECRET_KEY
echo $RIFTECH_ADMIN_USERNAME
echo $RIFTECH_ADMIN_PASSWORD

# Check all at once
env | grep RIFTECH
```

### Test in Python:

```python
import os

print(f"SECRET_KEY set: {bool(os.getenv('RIFTECH_SECRET_KEY'))}")
print(f"ADMIN_USERNAME set: {bool(os.getenv('RIFTECH_ADMIN_USERNAME'))}")
print(f"ADMIN_PASSWORD set: {bool(os.getenv('RIFTECH_ADMIN_PASSWORD'))}")
```

---

## 🛡️ Security Best Practices

### ✅ DO:
- Use strong, random secret keys (32+ characters)
- Use strong passwords (minimum 12 characters)
- Limit file permissions (chmod 600)
- Change credentials regularly
- Use different passwords for different systems
- Store secrets securely (e.g., AWS Secrets Manager, HashiCorp Vault)
- Rotate secret keys periodically (every 90 days)
- Use environment-specific keys (dev, staging, prod)

### ❌ DON'T:
- Commit environment files to git
- Use default credentials in production
- Share credentials via email/chat
- Hardcode secrets in source code
- Use simple/predictable passwords
- Reuse passwords across systems
- Store secrets in plain text files

---

## 📝 Example Complete Setup

### For Production Deployment:

```bash
# 1. Generate random secret key
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Secret Key: $SECRET_KEY"

# 2. Generate strong password
PASSWORD=$(python -c "import secrets, string; chars = string.ascii_letters + string.digits + string.punctuation; print(''.join(secrets.choice(chars) for _ in range(20)))")
echo "Password: $PASSWORD"

# 3. Create environment directory
sudo mkdir -p /etc/riftech-security

# 4. Create environment file
sudo tee /etc/riftech-security/environment > /dev/null <<EOF
RIFTECH_SECRET_KEY=$SECRET_KEY
RIFTECH_ADMIN_USERNAME=riftech_admin
RIFTECH_ADMIN_PASSWORD=$PASSWORD
EOF

# 5. Set secure permissions
sudo chmod 600 /etc/riftech-security/environment
sudo chown root:root /etc/riftech-security/environment

# 6. Update systemd service
sudo sed -i '/\[Service\]/a EnvironmentFile=/etc/riftech-security/environment' \
    /etc/systemd/system/riftech-security-v2.service

# 7. Reload and restart services
sudo systemctl daemon-reload
sudo systemctl restart riftech-security-v2
sudo systemctl restart riftech-web-server

# 8. Verify services are running
sudo systemctl status riftech-security-v2
sudo systemctl status riftech-web-server
```

---

## 🐛 Troubleshooting

### Issue 1: Environment variables not loading

**Symptoms:**
- Authentication fails
- Services using default credentials

**Solutions:**
```bash
# Check if variables are set
echo $RIFTECH_SECRET_KEY

# Restart with fresh shell
exec bash

# Check service environment
sudo systemctl show riftech-security-v2 -p Environment
```

---

### Issue 2: Permission denied on environment file

**Solutions:**
```bash
# Fix permissions
sudo chmod 600 /etc/riftech-security/environment

# Fix ownership
sudo chown root:root /etc/riftech-security/environment
```

---

### Issue 3: Service fails to start

**Debug steps:**
```bash
# Check service logs
sudo journalctl -u riftech-security-v2 -n 50

# Check if environment file is accessible
sudo cat /etc/riftech-security/environment

# Test manually
cd ~/riftech-cam-security-pro
python main_v2.py
```

---

## 🔄 Rotating Credentials

### Change Secret Key:

```bash
# 1. Generate new key
NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. Update environment file
sudo sed -i "s/^RIFTECH_SECRET_KEY=.*/RIFTECH_SECRET_KEY=$NEW_SECRET/" \
    /etc/riftech-security/environment

# 3. Restart services
sudo systemctl restart riftech-security-v2
sudo systemctl restart riftech-web-server

# 4. Users will need to re-login (existing tokens invalidated)
```

### Change Admin Password:

```bash
# 1. Generate new password
NEW_PASSWORD=$(python -c "import secrets, string; chars = string.ascii_letters + string.digits + string.punctuation; print(''.join(secrets.choice(chars) for _ in range(20)))")

# 2. Update environment file
sudo sed -i "s/^RIFTECH_ADMIN_PASSWORD=.*/RIFTECH_ADMIN_PASSWORD=$NEW_PASSWORD/" \
    /etc/riftech-security/environment

# 3. Restart services
sudo systemctl restart riftech-security-v2
sudo systemctl restart riftech-web-server
```

---

## 📦 Quick Setup Script

Save this as `setup_env.sh` and run:

```bash
#!/bin/bash
# setup_env.sh - Quick environment setup

# Generate random values
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ADMIN_USERNAME="riftech_$(python3 -c "import secrets; print(secrets.token_hex(3))")"
ADMIN_PASSWORD=$(python3 -c "import secrets, string; chars = string.ascii_letters + string.digits + string.punctuation; print(''.join(secrets.choice(chars) for _ in range(20)))")

# Create environment file
sudo mkdir -p /etc/riftech-security
sudo tee /etc/riftech-security/environment > /dev/null <<EOF
RIFTECH_SECRET_KEY=$SECRET_KEY
RIFTECH_ADMIN_USERNAME=$ADMIN_USERNAME
RIFTECH_ADMIN_PASSWORD=$ADMIN_PASSWORD
EOF

# Set permissions
sudo chmod 600 /etc/riftech-security/environment
sudo chown root:root /etc/riftech-security/environment

# Display credentials (SAVE THESE!)
echo "================================"
echo "CREDENTIALS GENERATED"
echo "================================"
echo "Admin Username: $ADMIN_USERNAME"
echo "Admin Password: $ADMIN_PASSWORD"
echo "================================"
echo ""
echo "Credentials saved to: /etc/riftech-security/environment"
echo ""
echo "Next steps:"
echo "1. Update systemd services to use EnvironmentFile"
echo "2. Restart services: sudo systemctl restart riftech-security-v2 riftech-web-server"
```

Run it:
```bash
chmod +x setup_env.sh
sudo ./setup_env.sh
```

---

## 📚 Additional Resources

- [Python Secrets Documentation](https://docs.python.org/3/library/secrets.html)
- [OpenSSL Documentation](https://www.openssl.org/docs/)
- [Systemd Environment Variables](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
- [OWASP Secret Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

## ✅ Checklist

- [ ] Generate random secret key
- [ ] Set admin username
- [ ] Set strong admin password
- [ ] Create environment file
- [ ] Set secure file permissions (600)
- [ ] Update systemd service configuration
- [ ] Reload systemd daemon
- [ ] Restart services
- [ ] Verify services running
- [ ] Test login with new credentials
- [ ] Save credentials securely

---

**Last Updated:** 2026-01-21
**Version:** 2.0.0
