FROM python:3.12-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Fetch logchecker.phar from GitHub releases
RUN curl -fSL -o /tmp/logchecker \
    "https://github.com/OPSnet/Logchecker/releases/latest/download/logchecker.phar" && \
    chmod +x /tmp/logchecker

FROM python:3.12-slim

# Install PHP CLI (required to run logchecker.phar)
RUN apt-get update && \
    apt-get install -y --no-install-recommends php-cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy logchecker binary from builder
COPY --from=builder /tmp/logchecker /usr/local/bin/logchecker

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user and set up logs directory
RUN useradd --create-home appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5050

CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "4", "--log-level", "warning", "--log-file", "/app/logs/logchecker.log", "--access-logfile", "/app/logs/access.log", "--disable-redirect-access-to-syslog", "app:app"]
