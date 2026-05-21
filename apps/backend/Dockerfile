FROM python:3.11-slim

WORKDIR /app

# Install deps first (cached layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy source
COPY src/ ./src/

EXPOSE 8000

CMD ["sh", "-c", "uvicorn job_copilot_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
