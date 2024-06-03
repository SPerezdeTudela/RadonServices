# syntax=docker/dockerfile:1
FROM python:3.8-slim-buster

# Set the working directory to /app
WORKDIR /app

# Install system dependencies
RUN apt-get update
RUN apt-get install -y build-essential python3-dev libpq-dev gfortran libopenblas-dev

# Clean up package lists to reduce image size
RUN rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the image
COPY dino_generated_requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Invoke entrypoint script
CMD ["python", "-u", "src/entry.py"]
