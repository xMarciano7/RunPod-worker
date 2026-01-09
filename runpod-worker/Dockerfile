FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /app

# --- PYTORCH CUDA (CRÍTICO) ---
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cu121

# Requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# App
COPY handler.py .

CMD ["python", "handler.py"]
