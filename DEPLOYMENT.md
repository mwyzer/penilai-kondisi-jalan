# Deployment Guide — Road Condition Assessor

Two main options: **Streamlit Cloud** (easiest, free) or **VPS** (full control, costs money).

---

## Option 1: Streamlit Cloud (Easiest)

### Prerequisites
- GitHub account (free at github.com)
- Streamlit Community Cloud account (free at share.streamlit.io)
- Push your code to a public GitHub repo

### Step 1: Push to GitHub

```bash
# Create a new repo on github.com (e.g., github.com/yourusername/road-condition-assessor)
# Then:

git remote add origin https://github.com/yourusername/road-condition-assessor.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Streamlit Cloud

1. Go to **https://share.streamlit.io**
2. Click **"New app"**
3. Fill in:
   - **GitHub repo**: `yourusername/road-condition-assessor`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Click **Deploy**

Streamlit will build and host your app at: `https://<your-app-name>.streamlit.app`

### Step 3: Add Secrets (API Keys)

In Streamlit Cloud dashboard:
1. Click your app → **Settings** ⚙️
2. Go to **Secrets**
3. Paste your `.streamlit/secrets.toml` content:
   ```toml
   AI_PROVIDER = "deepseek"
   DEEPSEEK_API_KEY = "sk-..."
   # ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Save and redeploy

**App will restart automatically with your secrets.**

### Pros
- ✅ Free tier (up to 3 apps)
- ✅ Automatic deployments on every git push
- ✅ No server to manage
- ✅ HTTPS by default
- ✅ Easy to share link

### Cons
- ❌ ~500 MB memory limit (fine for this app)
- ❌ File storage lost on restart (segment data not persistent — use export/import)
- ❌ Slower than VPS
- ❌ Streamlit Cloud controls infrastructure

### Persistence (Important!)

**Streamlit Cloud does NOT persist `data/segmen.json` between restarts.**

Solutions:
1. **Export before closing**: download CSV/GeoJSON at end of session
2. **Use database** (upgrade): set up PostgreSQL/Firebase to persist data (requires paid Streamlit tier or external service)
3. **Manual persistence**: user re-imports CSV on next session

---

## Option 2: VPS Deployment (Full Control)

### Prerequisites
- VPS with Ubuntu 20.04+ (e.g., DigitalOcean $5/mo, Linode, Hetzner, AWS EC2)
- SSH access to your VPS
- Domain name (optional, but recommended)

### Step 1: Set Up VPS

SSH into your server:
```bash
ssh root@your-vps-ip
```

Update system:
```bash
apt update && apt upgrade -y
```

Install Python and dependencies:
```bash
apt install -y python3.10 python3.10-venv python3-pip git nginx supervisor
```

### Step 2: Clone Repository

```bash
cd /home
git clone https://github.com/yourusername/road-condition-assessor.git
cd road-condition-assessor

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Create `.streamlit/secrets.toml`

```bash
mkdir -p .streamlit
cat > .streamlit/secrets.toml << 'EOF'
AI_PROVIDER = "deepseek"
DEEPSEEK_API_KEY = "sk-..."
# ANTHROPIC_API_KEY = "sk-ant-..."
EOF

# Protect it
chmod 600 .streamlit/secrets.toml
```

### Step 4: Configure Supervisor (Auto-restart)

Create `/etc/supervisor/conf.d/streamlit.conf`:
```bash
cat > /etc/supervisor/conf.d/streamlit.conf << 'EOF'
[program:streamlit]
directory=/home/road-condition-assessor
command=/home/road-condition-assessor/venv/bin/streamlit run app.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --logger.level=info
autostart=true
autorestart=true
stderr_logfile=/var/log/streamlit_err.log
stdout_logfile=/var/log/streamlit_out.log
user=root
environment=PATH="/home/road-condition-assessor/venv/bin"
EOF
```

Enable and start:
```bash
supervisorctl reread
supervisorctl update
supervisorctl start streamlit
```

Check status:
```bash
supervisorctl status streamlit
```

### Step 5: Configure Nginx (Reverse Proxy)

Create `/etc/nginx/sites-available/streamlit`:
```bash
cat > /etc/nginx/sites-available/streamlit << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Enable the site:
```bash
ln -s /etc/nginx/sites-available/streamlit /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Step 6: SSL Certificate (HTTPS)

Install Certbot:
```bash
apt install -y certbot python3-certbot-nginx
```

Get certificate:
```bash
certbot --nginx -d your-domain.com
```

Auto-renew:
```bash
systemctl enable certbot.timer
systemctl start certbot.timer
```

### Step 7: Persistent Data

Create a dedicated data directory:
```bash
mkdir -p /home/road-condition-assessor/data
chown root:root /home/road-condition-assessor/data
chmod 755 /home/road-condition-assessor/data
```

The `data/segmen.json` will persist across restarts.

### Access Your App

Visit: `https://your-domain.com` (if you set up SSL)

---

## Comparison Table

| Feature | Streamlit Cloud | VPS |
|---------|-----------------|-----|
| **Setup time** | 5 minutes | 30 minutes |
| **Cost** | Free ($20/mo premium) | $5–50+/mo |
| **Data persistence** | ❌ Lost on restart | ✅ Persistent |
| **Control** | Limited | Full |
| **Scalability** | Limited | Unlimited |
| **SSL/HTTPS** | ✅ Automatic | ✅ Free (Certbot) |
| **Uptime** | 99.9% | Depends on provider |
| **Server management** | None | Required |
| **Recommended for** | Teams, demos, small groups | Production, long-term use |

---

## VPS Providers (Recommendations)

| Provider | Price | Notes |
|----------|-------|-------|
| **DigitalOcean** | $5/mo | Simple, good docs, $200 free credit |
| **Linode** | $5/mo | Reliable, great support |
| **Hetzner** | €3/mo | Very cheap (EU-based) |
| **AWS EC2** | Free tier, then $$ | Most flexible, steepest learning curve |
| **Vultr** | $2.50/mo | Cheap, good performance |

---

## Monitoring and Logs (VPS)

Check app status:
```bash
supervisorctl status streamlit
```

View logs:
```bash
tail -f /var/log/streamlit_out.log
tail -f /var/log/streamlit_err.log
```

Restart app:
```bash
supervisorctl restart streamlit
```

---

## Troubleshooting

### "App not responding" on Streamlit Cloud
- Check **Settings → Advanced settings → Custom headers** for any issues
- Restart the app manually in the dashboard
- Check logs: **Settings → Logs**

### "Connection refused" on VPS
```bash
# Check if Streamlit is running
supervisorctl status streamlit

# Check if port 8501 is listening
netstat -tuln | grep 8501

# Restart Nginx
systemctl restart nginx
```

### "Secrets not loading"
- VPS: ensure `.streamlit/secrets.toml` exists and is readable
- Streamlit Cloud: re-save secrets and redeploy
- Both: restart the app

### "Data not persisting" on Streamlit Cloud
- Expected behavior. Export data before closing.
- Consider upgrading to paid tier with persistent storage.

---

## Quick Summary

**Choose Streamlit Cloud if:**
- You want to share quickly
- No persistent data needed (or users export CSV)
- Free tier is enough
- Don't want to manage servers

**Choose VPS if:**
- You need persistent data (`data/segmen.json`)
- Want full control
- Planning long-term production use
- Have budget for hosting

---

## Next Steps

1. **Streamlit Cloud**: Push to GitHub → deploy at share.streamlit.io
2. **VPS**: Rent a server → follow steps above → access via domain

Questions? Check Streamlit docs: https://docs.streamlit.io/deploy
