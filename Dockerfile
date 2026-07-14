# Use official Python runtime as a parent image
FROM python:3.10.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (required for PyMuPDF and SpaCy)
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download the spaCy model explicitly
RUN python -m spacy download en_core_web_sm

# Copy the current directory contents into the container at /app
COPY . .

# Expose the port the app runs on (HF Spaces uses 7860 by default)
EXPOSE 7860

# Command to run the FastAPI application
CMD ["uvicorn", "src.generation.api:app", "--host", "0.0.0.0", "--port", "7860"]
