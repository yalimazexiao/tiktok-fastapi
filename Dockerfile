FROM python:3.10-slim

WORKDIR /app

# 安装必要的依赖
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libgbm1 \
    libgtk-3-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# 先复制requirements.txt可以更好地利用Docker缓存
COPY requirements.txt .

# 安装Python依赖和Playwright
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium \
    && playwright install-deps

# 复制应用代码
COPY . .

EXPOSE 8000

# 使用生产模式运行
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
