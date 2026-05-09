FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies required by some Python packages (e.g. gcc for psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy both requirements files so Docker layer cache is invalidated only when deps change
COPY requirements.txt .
COPY saas/requirements.txt saas-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r saas-requirements.txt

# Copy application code
COPY tradingagents/ tradingagents/
COPY saas/ saas/
COPY pyproject.toml .

# Cloud Run injects PORT at runtime (default 8080)
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn saas.api.main:app --host 0.0.0.0 --port ${PORT}"]
