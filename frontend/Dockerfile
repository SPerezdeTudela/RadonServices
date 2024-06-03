# syntax=docker/dockerfile:1
FROM python:3.9-slim-buster

# Set the working directory to /app
WORKDIR /app

# Install system dependencies
RUN apt-get update
RUN apt-get install -y build-essential curl software-properties-common

# Clean up package lists to reduce image size
RUN rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the image
COPY dino_generated_requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port for Streamlit
EXPOSE 8501

# Add healthcheck url
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Invoke entrypoint script
ENTRYPOINT ["streamlit", "run", "./src/Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
