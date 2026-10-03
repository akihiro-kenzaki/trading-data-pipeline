# 1. Base image: Use official Python 3.12 slim variant
FROM python:3.12.15-slim

# Set the working directory inside the container
WORKDIR /app

# 2. Install dependencies (Leverage Docker layer caching by copying requirements.txt first)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files into the container
COPY . .

# 3. Set the default startup command
CMD ["python"]