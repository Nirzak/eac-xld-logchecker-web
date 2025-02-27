# eac-xld-logchecker-web

A Simple Web UI to check eac and xld log and view the report online.

## Requirements

* PHP 8.1+
* logchecker.phar file : [releases](https://github.com/OPSnet/Logchecker/releases) (Download and install it by the following command)

```bash
mv logchecker.phar /usr/local/bin/logchecker
chmod +x /usr/local/bin/logchecker
```

* Flask (pip3 install flask)
* Bleach (pip3 install bleach)


## Optional Requirements

* Python 3.5+
* [cchardet](https://github.com/PyYoshi/cChardet) (or [chardet](https://github.com/chardet/chardet))
* [eac_logchecker.py](https://github.com/OPSnet/eac_logchecker.py)
* [xld_logchecker.py](https://github.com/OPSnet/xld_logchecker.py)

```bash
pip3 install cchardet eac-logchecker xld-logchecker
```

## Run the Web App & Use

```bash
python3 app.py
```

## To run in a Production Envrionment

```bash
sudo apt install gunicorn

gunicorn --workers=<number-of-your-worker> app:app --daemon
```

## Nginx Reverse Proxy Config

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




