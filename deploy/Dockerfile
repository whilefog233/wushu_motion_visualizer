# 可选：Docker 部署
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（OpenCV 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-api.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

COPY . .

ENV KUNGFU_API_KEY=请替换
ENV KUNGFU_CORS_ORIGIN=https://kungfu-v3-wushu.hybrid-j9y56-1505.chatgpt.site
ENV KUNGFU_MAX_CONCURRENT=1

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
