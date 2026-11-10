
# --------------------------------------------------
# Base Python Image
# --------------------------------------------------

# Use Python 3.11 to match the local development environment.
FROM python:3.11-slim

# Prevent Python from generating .pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Display Python logs immediately in Docker logs.
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container.
WORKDIR /app


# --------------------------------------------------
# System Dependencies
# --------------------------------------------------

# Install system packages required by Python dependencies.
# libgomp1 supports certain machine-learning libraries.
# gcc and build-essential support packages that need compilation.

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*


# --------------------------------------------------
# Python Dependencies
# --------------------------------------------------

# Copy the dependency list first.
# This allows Docker to reuse the dependency layer
# when application source code changes.

COPY requirements.txt .

# Install Python dependencies.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# --------------------------------------------------
# Application Source Code
# --------------------------------------------------

# Copy the backend source code into the container.
COPY src/ ./src/

# Make the devpilot package available to Python.
ENV PYTHONPATH=/app/src


# --------------------------------------------------
# FastAPI Server
# --------------------------------------------------

# Document the port used by FastAPI.
EXPOSE 8000

# Start the FastAPI application using Uvicorn.
CMD ["uvicorn", "devpilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
