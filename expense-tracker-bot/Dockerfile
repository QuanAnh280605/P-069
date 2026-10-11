FROM python:3.11-slim

WORKDIR /app

# Cài đặt timezone và dependencies hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Ho_Chi_Minh
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Tạo thư mục data cho SQLite volume persistence
RUN mkdir -p /app/data

CMD ["python", "main.py"]
