FROM mcr.microsoft.com/devcontainers/javascript-node:5.2.5-24-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        python3 \
        pkg-config \
        libgtk-3-0 \
        libnss3 \
        libgbm1 \
        libasound2 \
        libatk-bridge2.0-0 \
        libdrm2 \
        libxkbcommon0 \
        libxss1 \
        xvfb \
    && rm -rf /var/lib/apt/lists/*
