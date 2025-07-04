FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y wget
COPY . .
RUN pip install -r requirements.txt
RUN playwright install chromium
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
