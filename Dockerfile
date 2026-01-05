FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY worker/ ./worker/
COPY scripts/ ./scripts/

# Create directories
RUN mkdir -p temp logs

# Make scripts executable
RUN chmod +x scripts/*.sh 2>/dev/null || true

# Health check
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD bash scripts/health_check.sh || exit 1

# Run worker
CMD ["python", "-u", "worker/worker.py", "worker/config.yaml"]
