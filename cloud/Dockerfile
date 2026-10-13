# Multi-Objective Compression Selection - Cloud Ingestion Receiver
# Lightweight Python 3.11 Container for 24/7 Production Operation

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libzstd-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY cloud/ ./cloud/
COPY shared/ ./shared/
COPY edge/ ./edge/
COPY dashboard/ ./dashboard/

# Create logs directory for SQLite outcomes and telemetry snapshots
RUN mkdir -p logs data/camera_captures

# Expose TCP ingestion port and Streamlit dashboard port
EXPOSE 8765 8501

ENV PYTHONUNBUFFERED=1

# Default command starts the cloud receiver service
CMD ["python", "-m", "cloud.receiver", "--host", "0.0.0.0", "--port", "8765"]
