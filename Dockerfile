FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        gcc \
        python3-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p sessions downloads

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

CMD ["python3", "bot.py"]
