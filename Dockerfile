# VYOMNETRA Space Situational Awareness Production Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    VYOMNETRA_ENV=production \
    VYOMNETRA_LOG_LEVEL=INFO

CMD ["uvicorn", "vyomnetra.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
