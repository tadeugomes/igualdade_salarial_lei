# syntax=docker/dockerfile:1
FROM python:3.10-slim
WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libfreetype6-dev libpng-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copia todo o código (app.py, processor.py, etc.)
COPY . .

ENV PORT=8080
EXPOSE 8080
# app.py define "app = FastAPI(...)"
CMD ["uvicorn", "app:app", "--host","0.0.0.0","--port","8080"]
