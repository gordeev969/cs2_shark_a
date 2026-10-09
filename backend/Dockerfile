# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CS2_DATA_DIR=/data

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --uid 10001 --create-home analyzer \
    && mkdir -p /data \
    && chown analyzer:analyzer /data

COPY --chown=analyzer:analyzer backend/app /app/backend/app
USER analyzer
EXPOSE 8000

# 0.0.0.0 is necessary inside the container; Compose exposes no backend host port.
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
