# 📦 VYOMNETRA Production Deployment Guide

This guide covers deployment options for the VYOMNETRA SSA Platform across Docker Compose, Systemd, and Kubernetes Helm.

---

## 1. Docker Compose (Recommended for Single-Node Deployment)

Deploy the complete stack (FastAPI REST service, Prometheus, Grafana) with a single command:

```bash
docker-compose up -d
```

### Services Included:
- **vyomnetra-api**: Port 8000
- **prometheus**: Port 9090
- **grafana**: Port 3000 (Credentials: `admin` / `admin`)

---

## 2. Systemd Native Linux Service

To run VYOMNETRA as a background daemon on Ubuntu/Debian Linux:

```bash
# 1. Copy service file
sudo cp deploy/vyomnetra.service /etc/systemd/system/

# 2. Reload daemon & start service
sudo systemctl daemon-reload
sudo systemctl enable vyomnetra
sudo systemctl start vyomnetra

# 3. Check status
sudo systemctl status vyomnetra
```

---

## 3. Kubernetes Deployment via Helm

Deploy to Kubernetes clusters using the provided Helm chart:

```bash
# Install / Upgrade release
helm upgrade --install vyomnetra ./deploy/helm/vyomnetra --namespace ssa --create-namespace
```

---

## 4. Backup & Maintenance

Execute automated zero-downtime online database snapshot backups:

```bash
python scripts/backup_db.py
```
Backups are archived under `/home/kanak/.gemini/antigravity/backups/`.
