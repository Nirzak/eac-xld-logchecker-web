# audio-ripping-logchecker

A Simple Web UI to check EAC, XLD, dBpoweramp and Whipper log and view the report online.

## Run with Docker Compose [Recommended]

You can easily run the application using Docker Compose. Make sure you have Docker and Docker Compose installed.

```bash
docker-compose up -d
```

The web app will be available at `http://localhost:5050`.

## API Endpoint Usage

You can also use the `/api` endpoint to analyze log files programmatically. Submit a POST request with a multipart file upload:

```bash
curl -X POST https://<host>/api -F "logfile=@<file-path>"
```

**Example:**
```bash
curl -X POST http://localhost:5050/api -F "logfile=@my_log.log"
```

**Response (JSON):**
```json
{"checksum":"checksum_ok",
"combined":false,
"details":[],
"language":"en",
"ripper":"EAC",
"score":100,
"version":"1.6"
}
```

**Rate Limiting:** The API endpoint has rate limiting enabled. The default limit is 30 requests per minute. You can customize this by setting the `RATE_LIMIT` environment variable (e.g., `RATE_LIMIT=1000 per minute`).

## Steps for non docker environments

### Requirements

* PHP 8.2 and above
* logchecker.phar file : [releases]((https://github.com/Nirzak/logchecker-fork/releases) (Download and install it by the following command)

```bash
mv logchecker.phar /usr/local/bin/logchecker
chmod +x /usr/local/bin/logchecker
```

* Flask (pip3 install flask)
* Bleach (pip3 install bleach)


### Optional Requirements

* Python 3.10+
* [eac_logchecker.py](https://github.com/OPSnet/eac_logchecker.py)
* [xld_logchecker.py](https://github.com/OPSnet/xld_logchecker.py)

```bash
pip3 install eac-logchecker xld-logchecker
```

### Run the Web App & Use

```bash
python3 app.py
```

### To run in a Production Envrionment

```bash
sudo apt install gunicorn

gunicorn --workers=<number-of-your-worker> app:app --daemon
```

### Nginx Reverse Proxy Config

```
    location /logchecker/ {
        proxy_pass http://127.0.0.1:5050/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        rewrite ^/logchecker(/.*)$ $1 break;
    }
```


