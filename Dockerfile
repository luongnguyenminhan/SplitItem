FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV ENV=production

# Set working directory
WORKDIR /app

# Create non-root user
RUN addgroup --system appuser && \
    adduser --system --ingroup appuser appuser

# Ensure external config mount point exists and set ownership (so mounted files are accessible)
# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/* && pip install uv && uv pip install -r requirements.txt --system

# Copy application code
COPY app/ ./app/
COPY start.sh ./start.sh

# Make start.sh executable, fix line endings, and set ownership
RUN chmod +x start.sh && sed -i 's/\r$//' start.sh && chown appuser:appuser start.sh

VOLUME ["/app/config"]

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

CMD ["/bin/bash", "-c", "exec ./start.sh"]