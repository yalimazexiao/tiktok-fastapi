# ✅ 用官方 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装依赖工具和 Playwright 所需依赖（重点）
RUN apt-get update && apt-get install -y \
    wget curl gnupg unzip fonts-liberation libnss3 libxss1 libasound2 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdbus-1-3 libdrm2 libxcomposite1 libxdamage1 \
    libxrandr2 xdg-utils libgbm1 libgtk-3-0 libxshmfence1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 playwright 和浏览器
RUN pip install playwright && playwright install chromium

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
