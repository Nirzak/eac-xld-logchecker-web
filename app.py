from flask import Flask, render_template, request, send_file, url_for, make_response
import logging
import subprocess
import os
import tempfile
import json
import uuid
import bleach
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Configure logging
logging.basicConfig(
    level=logging.ERROR,  # Log only errors and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 200 * 1024  # 200KB
APPLICATION_ROOT = "/logchecker"  # Custom subpath for reverse proxy eg. nginx
ALLOWED_EXTENSIONS = {'log', 'txt'} # Allowed extensions

RESULTS_DIR = os.path.join(tempfile.gettempdir(), 'logchecker_results')
os.makedirs(RESULTS_DIR, exist_ok=True)

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
    logger.error(f"File upload exceeded MAX_CONTENT_LENGTH (200 KB): {str(e)}")
    return render_template('index.html', error="File size exceeds the maximum limit of 200 KB. Please upload a smaller file."), 413

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    details_json = None
    result_id = None

    if request.method == 'POST':
        if 'logfile' not in request.files:
            error = "No file part"
        else:
            file = request.files['logfile']
            if file.filename == '':
                error = "No file selected"
            elif not allowed_file(file.filename):
                error = "File type not allowed. Only .log and .txt files are permitted."
            else:
                safe_filename = secure_filename(file.filename)
                input_filepath = None
                html_output_filepath = None
                json_output_filepath = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='_' + safe_filename) as input_temp:
                        file.save(input_temp.name)
                        input_filepath = input_temp.name

                    try:
                        encoding = detect_encoding(input_filepath)
                        with open(input_filepath, 'r', encoding=encoding) as f:
                            f.read()
                    except UnicodeDecodeError:
                        error = "File is not a supported log file. Please try again with a valid UTF-8 or UTF-16 text file."
                        logger.error(f"Encoding detection failed for {input_filepath}: {str(e)}")
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
                            logger.error(f"Error generating outputs: {result.stderr}")
                        else:
                            with open(html_output_filepath, 'r', encoding='utf-8') as f:
                                raw_html = f.read()

                            # Sanitize the HTML, allowing only safe tags and attributes
                            allowed_tags = ['span', 'div', 'p', 'strong', 'em', 'br']  # Adjust based on logchecker output
                            allowed_attributes = {'span': ['class']}  # Allow class for styling
                            sanitized_html = bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attributes)

                            wrapped_html = f"""
                            <!DOCTYPE html>
                            <html lang="en">
                            <head>
                                <meta charset="UTF-8">
                                <title>Logchecker Result</title>
                                <link rel="stylesheet" href="{APPLICATION_ROOT}{url_for('serve_css')}">
                            </head>
                            <body>
                                <pre>{raw_html}</pre>
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

                except Exception as e:
                    error = "An error occurred. Please try again."
                    logger.error(f"Unexpected error in file processing: {str(e)}")
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

    return render_template('index.html', details=details_json, result_id=result_id, error=error)

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
