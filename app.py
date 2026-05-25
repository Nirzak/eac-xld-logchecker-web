from flask import Flask, render_template, request, send_file, url_for, make_response
import logging
import subprocess
import os
import tempfile
import json
import uuid
import bleach
import re
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Configure logging from environment variable
_LOG_LEVEL = os.environ.get('LOG_LEVEL', 'error').upper()
_VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
if _LOG_LEVEL not in _VALID_LOG_LEVELS:
    _LOG_LEVEL = 'ERROR'

_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
_LOG_FILE = '/app/logs/logchecker.log'

logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL),
    format=_LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),  # stdout → docker logs
        logging.FileHandler(_LOG_FILE),  # → /app/logs/logchecker.log
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 200 * 1024  # 200KB
raw_subpath = os.environ.get('SUBPATH', '/logchecker').strip()
if raw_subpath in ('', '/'):
    APPLICATION_ROOT = ''
else:
    if not raw_subpath.startswith('/'):
        raw_subpath = '/' + raw_subpath
    APPLICATION_ROOT = raw_subpath.rstrip('/')
ALLOWED_EXTENSIONS = {'log', 'txt'} # Allowed extensions

RESULTS_DIR = os.path.join(tempfile.gettempdir(), 'logchecker_results')
os.makedirs(RESULTS_DIR, exist_ok=True)

def _sanitize_for_log(value):
    """Sanitize a string for safe inclusion in log messages.

    Prevents log injection/forgery by stripping control characters,
    ANSI escape sequences, and newlines that could be used to forge
    log entries or obscure malicious activity.
    """
    # Remove ANSI escape sequences
    value = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', value)
    # Replace newlines and carriage returns to prevent log line injection
    value = value.replace('\n', '').replace('\r', '')
    # Strip other control characters (ASCII 0-31 except tab)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
    # Truncate to a reasonable length to prevent log flooding
    return value[:255]


def _get_client_ip():
    """Get the real client IP, respecting X-Forwarded-For behind a reverse proxy."""
    # X-Forwarded-For may contain: client, proxy1, proxy2
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        # Take the first (leftmost) IP — the original client
        ip = forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr or 'unknown'
    return _sanitize_for_log(ip)


def detect_encoding(filepath):
    """
    Attempt to detect if the file is UTF-8 or UTF-16 by trying both encodings.
    Returns the encoding if successful, or raises an exception if neither works.
    """
    encodings = ['utf-8', 'utf-16']
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                f.read()  # Attempt to read the entire file
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("File is not encoded in UTF-8 or UTF-16. Please use a valid text file.")

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file_error(e):
    client_ip = _get_client_ip()
    logger.warning(f"[{client_ip}] File upload exceeded MAX_CONTENT_LENGTH (200 KB)")
    return render_template('index.html', error="File size exceeds the maximum limit of 200 KB. Please upload a smaller file."), 413

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    details_json = None
    result_id = None

    if request.method == 'POST':
        client_ip = _get_client_ip()
        if 'logfile' not in request.files:
            error = "No file part"
            logger.info(f"[{client_ip}] Upload attempt with no file part")
        else:
            file = request.files['logfile']
            if file.filename == '':
                error = "No file selected"
                logger.info(f"[{client_ip}] Upload attempt with empty filename")
            elif not allowed_file(file.filename):
                error = "File type not allowed. Only .log and .txt files are permitted."
                safe_name = _sanitize_for_log(secure_filename(file.filename))
                logger.warning(f"[{client_ip}] Rejected disallowed file type: {safe_name}")
            else:
                safe_filename = secure_filename(file.filename)
                input_filepath = None
                html_output_filepath = None
                json_output_filepath = None
                safe_name_log = _sanitize_for_log(safe_filename)
                logger.info(f"[{client_ip}] Checking file: {safe_name_log}")
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='_' + safe_filename) as input_temp:
                        file.save(input_temp.name)
                        input_filepath = input_temp.name

                    try:
                        encoding = detect_encoding(input_filepath)
                        with open(input_filepath, 'r', encoding=encoding) as f:
                            log_content = f.read()
                            
                        is_rdbarr = False
                        if "Lenovo  Slim_USB_Burner" in log_content:
                            is_rdbarr = True
                        elif re.search(r'Filename\s+[A-Za-z]:\\\d+\.', log_content):
                            is_rdbarr = True

                    except UnicodeDecodeError:
                        error = "File is not a supported log file. Please try again with a valid UTF-8 or UTF-16 text file."
                        logger.warning(f"[{client_ip}] Encoding detection failed for file: {safe_name_log}")
                        if input_filepath is not None and os.path.exists(input_filepath):
                            try:
                                os.remove(input_filepath)
                            except Exception as e:
                                logger.error(f"Error removing input file {input_filepath}: {str(e)}")
                    else:
                        html_fd, html_output_filepath = tempfile.mkstemp(suffix='.html')
                        os.close(html_fd)
                        json_fd, json_output_filepath = tempfile.mkstemp(suffix='.json')
                        os.close(json_fd)
                        
                        command = ['logchecker', 'analyze', input_filepath, html_output_filepath, json_output_filepath]
                        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        if result.returncode != 0:
                            error = "Failed to process the file. Please check your input and try again."
                            logger.error(f"[{client_ip}] Logchecker analysis failed for file: {safe_name_log}")
                            logger.debug(f"[{client_ip}] Logchecker stderr: {_sanitize_for_log(result.stderr)}")
                        else:
                            with open(html_output_filepath, 'r', encoding='utf-8') as f:
                                raw_html = f.read()

                            if is_rdbarr:
                                raw_html = '<div class="logchecker-notice" style="color: #ff4444; font-weight: bold; margin-bottom: 1rem;">Notice: rdbarr rip detected. Score reduced by 100.</div>\n' + raw_html

                            # Sanitize the HTML, allowing only safe tags and attributes
                            allowed_tags = ['span', 'div', 'p', 'strong', 'em', 'br']  # Adjust based on logchecker output
                            allowed_attributes = {'span': ['class'], 'div': ['class', 'style']}  # Allow style for our notice
                            sanitized_html = bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attributes)

                            wrapped_html = f"""
                            <!DOCTYPE html>
                            <html lang="en">
                            <head>
                                <meta charset="UTF-8">
                                <title>Logchecker Result</title>
                                <link rel="stylesheet" href="{APPLICATION_ROOT}{url_for('serve_log_css')}">
                            </head>
                            <body>
                                <pre>{sanitized_html}</pre>
                            </body>
                            </html>
                            """

                            with open(html_output_filepath, 'w', encoding='utf-8') as f:
                                f.write(wrapped_html)

                            result_id = uuid.uuid4().hex
                            result_path = os.path.join(RESULTS_DIR, f'{result_id}.html')
                            os.rename(html_output_filepath, result_path)
                            html_output_filepath = None

                            with open(json_output_filepath, 'r', encoding='utf-8') as f:
                                details_json = json.load(f)
                                
                            if is_rdbarr:
                                try:
                                    current_score = int(details_json.get('score', 100))
                                    details_json['score'] = current_score - 100
                                except ValueError:
                                    pass
                                
                                if 'details' not in details_json:
                                    details_json['details'] = []
                                details_json['details'].append("rdbarr rip detected. Score reduced by 100.")
                                details_json['rdbarr_rip'] = 'Yes'

                            score = details_json.get('score', 'N/A')
                            logger.info(f"[{client_ip}] Analysis complete for file: {safe_name_log} — score: {score}")

                except Exception as e:
                    error = "An error occurred. Please try again."
                    logger.error(f"[{client_ip}] Unexpected error processing file {safe_name_log}: {type(e).__name__}")
                    logger.debug(f"[{client_ip}] Exception details: {_sanitize_for_log(str(e))}")
                finally:
                    if input_filepath is not None and os.path.exists(input_filepath):
                        try:
                            os.remove(input_filepath)
                        except Exception as e:
                            logger.error(f"Error removing input file {input_filepath}: {str(e)}")
                    if json_output_filepath is not None and os.path.exists(json_output_filepath):
                        try:
                            os.remove(json_output_filepath)
                        except Exception as e:
                            logger.error(f"Error removing JSON file {json_output_filepath}: {str(e)}")

    return render_template('index.html', details=details_json, result_id=result_id, error=error, subpath=APPLICATION_ROOT)

@app.route('/result/<result_id>')
def serve_html(result_id):
    if not result_id.isalnum():
        return "Invalid result ID", 400
    result_path = os.path.join(RESULTS_DIR, f'{result_id}.html')
    if os.path.exists(result_path):
        try:
            response = make_response(send_file(result_path))
            os.remove(result_path)
            return response
        except Exception as e:
            logger.error(f"Error serving file: {str(e)}")
            return "An error occurred while serving the file. Please try again.", 500
    else:
        return "No result available", 404

@app.route('/style.css')
def serve_log_css():
    css_file = os.path.join(os.path.dirname(__file__), 'styles', 'log.css')
    if os.path.exists(css_file):
        return send_file(css_file)
    else:
        return "CSS not available", 404

@app.route('/main.css')
def serve_main_css():
    css_file = os.path.join(os.path.dirname(__file__), 'styles', 'main.css')
    if os.path.exists(css_file):
        return send_file(css_file)
    else:
        return "CSS not available", 404

@app.route('/main.js')
def serve_main_js():
    js_file = os.path.join(os.path.dirname(__file__), 'scripts', 'main.js')
    if os.path.exists(js_file):
        return send_file(js_file)
    else:
        return "JS not available", 404

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' fonts.googleapis.com 'unsafe-inline'; font-src fonts.gstatic.com; frame-ancestors 'none';"
    return response

if __name__ == '__main__':
    app.run('0.0.0.0', port=5050, debug=True)
