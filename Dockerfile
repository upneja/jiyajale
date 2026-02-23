FROM python:3.13-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch first (much smaller than CUDA version)
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Python dependencies (skip torch/torchaudio since already installed)
COPY requirements.txt .
RUN grep -v -E "^(torch==|torchaudio==|nvidia|triton|cuda)" requirements.txt > requirements-filtered.txt \
    && pip install --no-cache-dir -r requirements-filtered.txt

# Frontend build
COPY frontend/package*.json frontend/
RUN cd frontend && npm ci

COPY frontend/ frontend/
RUN cd frontend && npm run build

# Backend code
COPY backend/ backend/
COPY separate.sh .
COPY pytest.ini .

# Serve frontend build from FastAPI
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV DEMUCS_MODEL=htdemucs

EXPOSE 8000

CMD ["/bin/sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
