# Sử dụng base image Python
FROM python:3.9-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements và cài đặt dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code ứng dụng vào thư mục làm việc
COPY . .

# Expose cổng mà ứng dụng Flask sẽ chạy
EXPOSE 5000

# Lệnh để chạy ứng dụng khi container khởi động
# Sử dụng gunicorn cho môi trường giống production hơn (tùy chọn)
# RUN pip install gunicorn
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
# Hoặc chạy trực tiếp với Flask (dễ hơn cho demo)
CMD ["python", "app.py"]