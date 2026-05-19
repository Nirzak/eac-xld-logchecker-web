FROM python:3.12-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates jq && \
    rm -rf /var/lib/apt/lists/*

# Fetch latest logchecker.phar from GitHub releases
RUN DOWNLOAD_URL=$(curl -s https://api.github.com/repos/OPSnet/Logchecker/releases/latest \
        | jq -r '.assets[] | select(.name == "logchecker.phar") | .browser_download_url') && \
    curl -fSL -o /tmp/logchecker "$DOWNLOAD_URL" && \
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
RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove g++ && \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN mkdir -p /app/logs

EXPOSE 5050

CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "4", "--log-level", "warning", "--log-file", "/app/logs/logchecker.log", "--access-logfile", "/app/logs/access.log", "--disable-redirect-access-to-syslog", "app:app"]
