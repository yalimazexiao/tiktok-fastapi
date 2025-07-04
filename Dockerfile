# 使用官方 Python 3.10 轻量版镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（Playwright 运行需要）
RUN apt-get update && apt-get install -y \
    wget curl gnupg unzip fonts-liberation libnss3 libxss1 libasound2 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdbus-1-3 libdrm2 libxcomposite1 libxdamage1 \
    libxrandr2 xdg-utils libgbm1 libgtk-3-0 libxshmfence1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（不包含 playwright）
RUN pip install --no-cache-dir -r requirements.txt

# 单独安装 playwright 和下载 chromium 浏览器
RUN pip install playwright
RUN playwright install chromium

# 复制项目所有代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动 FastAPI 服务，监听所有接口，端口 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
