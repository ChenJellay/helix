FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY ui/ ui/
COPY seed/ seed/

# Set Python path so `helix` package is importable
ENV PYTHONPATH=/app/src

EXPOSE 8000 8501
