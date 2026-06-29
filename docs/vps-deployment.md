# VPS Deployment Guide

## Prerequisites

An Ubuntu 22.04+ VPS with:
- Docker installed (`docker --version`)
- Docker Compose V2 installed (`docker compose version`)
- A non-root user with sudo access

If Docker is not installed, run:
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

## First-Time Setup

### 1. Create Application User

```bash
sudo useradd -m -s /bin/bash agentuser
sudo usermod -aG docker agentuser
sudo su - agentuser
```

### 2. Clone the Repository

```bash
cd /home/agentuser
git clone https://github.com/yourusername/operation-drake.git
cd operation-drake
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env   # fill in TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, etc.
chmod 600 .env
```

### 4. Start Services

```bash
docker compose up -d
docker compose logs -f
```

### 5. Verify Health

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","database":"connected",...}
```

## Auto-Restart on Reboot

Docker Compose uses `restart: unless-stopped` — services restart automatically after reboot. No additional configuration needed.

## Updating the Deployment

```bash
git pull
docker compose build
docker compose up -d
```

This does a rolling update — the old container stays running until the new one starts.

## Viewing Logs

```bash
docker compose logs -f           # all services
docker compose logs -f api       # API service only
docker compose logs -f telegram  # Telegram service only
```

## Database Backup

```bash
# Manual backup
cp data/database/agent.db data/database/agent-$(date +%Y%m%d).db

# Automated daily backup (add to crontab with: crontab -e)
0 2 * * * cd /home/agentuser/operation-drake && cp data/database/agent.db data/database/agent-$(date +\%Y\%m\%d).db
```

## Smoke Test

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:8000/tasks | python3 -m json.tool
```

## Rollback

To roll back to the previous image:
```bash
docker compose down
git checkout HEAD~1  # or the specific commit
docker compose build
docker compose up -d
```

## Firewall Notes

The API binds to port 8000. If you want to expose it publicly, open the port:
```bash
sudo ufw allow 8000/tcp
```

For production, consider putting Nginx in front as a reverse proxy with TLS. This is not required for personal use with Telegram long polling.

## Security Checklist

- [ ] `.env` has permissions `600` (`chmod 600 .env`)
- [ ] `.env` is not committed to Git
- [ ] Bot token is not shared or logged
- [ ] No API keys in docker-compose.yml (use `env_file`)
- [ ] Data directory is not publicly accessible
