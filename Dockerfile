FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY daylapse ./daylapse
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/data/captures

CMD ["daylapse-recorder"]
