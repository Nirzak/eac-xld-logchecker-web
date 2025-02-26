from flask import Flask, render_template, request, send_file, url_for
import subprocess
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Store paths for generated files
generated_html_path = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    global generated_html_path
    output_url = None

    if request.method == 'POST':
        if 'logfile' not in request.files:
            return "No file part", 400
        
        file = request.files['logfile']
        if file.filename == '':
            return "No file selected", 400
        
        safe_filename = secure_filename(file.filename)
        
        try:
            # Save uploaded file securely
            with tempfile.NamedTemporaryFile(delete=False, suffix='_' + safe_filename) as input_temp:
                file.save(input_temp.name)
                input_filepath = input_temp.name

            # Create temporary files for HTML and JSON outputs
            html_fd, html_output_filepath = tempfile.mkstemp(suffix='.html')
            os.close(html_fd)
            
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

            # Generate URL for the iframe to load the HTML
            output_url = url_for('serve_html', _external=False) #uncomment to server using iframe
        
        finally:
            # Clean up the uploaded input file
            if os.path.exists(input_filepath):
                os.remove(input_filepath)
    
    return render_template('index.html', output_url=output_url, details=details_summary)

@app.route('/result')
def serve_html():
    global generated_html_path
    if generated_html_path and os.path.exists(generated_html_path):
        return send_file(generated_html_path)
    else:
        return "No result available", 404

if __name__ == '__main__':
    app.run('127.0.0.1',port=5050,debug=True)