FROM python:3.11-slim

WORKDIR /app

# Copy everything in the build context (apps/backend/)
COPY apps/backend/pyproject.toml ./
COPY apps/backend/src/ ./src/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn job_copilot_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
