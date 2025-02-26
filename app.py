from flask import Flask, render_template, request, send_file, url_for
import subprocess
import os
import tempfile
import sass
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)

APPLICATION_ROOT = "/logchecker"

# Only allow certain file types
ALLOWED_EXTENSIONS = {'log', 'txt'}

# Store paths for generated files
generated_html_path = None
compiled_css_path = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Compile SCSS to CSS
def compile_scss(scss_file_path):
    with open(scss_file_path, 'r') as f:
        scss_content = f.read()
    css_output = sass.compile(string=scss_content)
    return css_output


@app.route('/', methods=['GET', 'POST'])
def index():
    global generated_html_path, compiled_css_path
    output_url = None
    details_summary = {}

    if request.method == 'POST':
        if 'logfile' not in request.files:
            return "No file part", 400
        
        file = request.files['logfile']
        if file.filename == '':
            return "No file selected", 400
        
        if not allowed_file(file.filename):
            return "File type not allowed. Only .log and .txt files are permitted.", 400
        
        safe_filename = secure_filename(file.filename)
        
        try:
            # Save uploaded file securely
            with tempfile.NamedTemporaryFile(delete=False, suffix='_' + safe_filename) as input_temp:
                file.save(input_temp.name)
                input_filepath = input_temp.name

            # Create temporary files for HTML and json outputs
            html_fd, html_output_filepath = tempfile.mkstemp(suffix='.html')
            os.close(html_fd)
            json_fd, json_output_filepath = tempfile.mkstemp(suffix='.json')
            os.close(json_fd)
            
            # Run the logchecker command to generate both outputs
            command = ['logchecker', 'analyze', input_filepath, html_output_filepath, json_output_filepath]
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                error_message = result.stderr or "Error generating outputs"
                return f"Error: {error_message}", 500

            # Read the generated HTML output
            with open(html_output_filepath, 'r', encoding='utf-8') as f:
                raw_html = f.read()

            # Wrap the content in <pre> tag
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

            # Save the wrapped HTML
            with open(html_output_filepath, 'w', encoding='utf-8') as f:
                f.write(wrapped_html)

            # Store the HTML path for serving
            generated_html_path = html_output_filepath

            # Read and parse the JSON details
            with open(json_output_filepath, 'r', encoding='utf-8') as f:
                details_json = json.load(f)
            # Exclude the "details" key
            details_summary = {k: v for k, v in details_json.items() if k != 'details'}

            # Compile SCSS to CSS
            css_fd, css_filepath = tempfile.mkstemp(suffix='.css')
            os.close(css_fd)
            compiled_css = compile_scss('styles/log.scss')
            with open(css_filepath, 'w') as css_file:
                css_file.write(compiled_css)
            compiled_css_path = css_filepath

            # Generate URL for the iframe to load the HTML

            output_url = url_for('serve_html', _external=False)
            output_url = f"{APPLICATION_ROOT}{output_url}"
            
        
        finally:
            # Clean up the uploaded input file
            if os.path.exists(input_filepath):
                os.remove(input_filepath)
            if os.path.exists(json_output_filepath):
                os.remove(json_output_filepath)
    
    return render_template('index.html', output_url=output_url, details=details_summary)

@app.route('/result')
def serve_html():
    global generated_html_path
    if generated_html_path and os.path.exists(generated_html_path):
        return send_file(generated_html_path)
    else:
        return "No result available", 404

@app.route('/style.css')
def serve_css():
    global compiled_css_path
    if compiled_css_path and os.path.exists(compiled_css_path):
        #return send_file(compiled_css_path, mimetype='text/css')
        return send_file(compiled_css_path)
    else:
        return "CSS not available", 404

if __name__ == '__main__':
    app.run('127.0.0.1',port=5050,debug=True)