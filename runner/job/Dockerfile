FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends chromium chromium-driver xvfb fluxbox fonts-liberation fonts-noto-color-emoji && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir selenium==4.35.0 flask==3.1.2
WORKDIR /job
COPY server.py .
CMD ["python","server.py"]
