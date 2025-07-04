# ✅ 官方 Playwright + Python 镜像（含浏览器环境）
FROM mcr.microsoft.com/playwright/python:v1.43.1-jammy

# 设置工作目录
WORKDIR /app

# 复制所有代码到容器中
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# ✅ 安装 Playwright 浏览器内核（关键一步）
RUN playwright install --with-deps

# 暴露端口
EXPOSE 8000

# 启动 FastAPI 应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
