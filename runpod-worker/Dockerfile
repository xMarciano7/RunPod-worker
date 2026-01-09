FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    fontconfig \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Torch CUDA 12.1 (cuDNN 8 compatible)
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cu121

COPY requirements.txt .
RUN pip install -r requirements.txt

# Fuentes
COPY fonts /usr/share/fonts/truetype/custom
RUN fc-cache -f -v

COPY handler.py .

CMD ["python", "handler.py"]
