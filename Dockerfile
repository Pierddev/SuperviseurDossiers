# ─────────────────────────────────────────────
#  SuperviseurDossiers — Dockerfile
#  Base: python:3.12-slim (Debian Bookworm)
#  Runs main.py directly (no PyInstaller)
# ─────────────────────────────────────────────

FROM python:3.12-slim

# Metadata
LABEL maintainer="SuperviseurDossiers"
LABEL description="Folder monitoring application with Flask intranet interface"

# Working directory in the container
WORKDIR /app

# System dependencies required for mysql-connector-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev-compat \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements-docker.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy application source code
COPY . .

# Port exposed for Flask intranet
EXPOSE 5000

# Entry point: direct execution of the Python script
CMD ["python", "main.py"]
