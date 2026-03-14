# Build stage: install dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install only production dependencies (no pytest)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --user -r requirements-prod.txt

# Runtime stage: minimal image
FROM python:3.12-slim

WORKDIR /app

# Create non-root user for security
RUN adduser --disabled-password --gecos "" appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local
RUN chown -R appuser:appuser /home/appuser/.local

# Copy application code
COPY app/ ./app/
RUN chown -R appuser:appuser /app

# Ensure .local/bin is in PATH for the appuser
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

EXPOSE 8000

# Environment variables can be overridden at runtime
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
