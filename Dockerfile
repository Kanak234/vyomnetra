# VYOMNETRA Space Situational Awareness Production Dockerfile
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -d /home/appuser -m -s /bin/false appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

WORKDIR /app
COPY . .

# Ensure appuser owns application dir and local share
RUN chown -R appuser:appuser /app && \
    mkdir -p /home/appuser/.local/share/vyomnetra && \
    chown -R appuser:appuser /home/appuser/.local

USER appuser:appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    VYOMNETRA_ENV=production \
    VYOMNETRA_LOG_LEVEL=INFO \
    HOME=/home/appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "vyomnetra.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
