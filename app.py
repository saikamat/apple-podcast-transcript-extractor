import os
import subprocess
import xml.etree.ElementTree as ET
from flask import Flask, request, render_template, redirect, flash, jsonify
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import time
from openai import RateLimitError
import logging
import traceback
from datetime import datetime

# Set up logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create a console handler for immediate feedback during development
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logging.getLogger().addHandler(console_handler)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logging.error("OpenAI API key not found. Please check your .env file.")
    raise ValueError("OpenAI API key not found. Please check your .env file.")

# Initialize OpenAI client
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    logging.info("OpenAI client initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client: {str(e)}")
    raise

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", 'supersecretkey')
app.config['UPLOAD_FOLDER'] = os.getenv("UPLOAD_FOLDER", './uploads')
app.config['ALLOWED_EXTENSIONS'] = {'ttml'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit upload size to 16MB

# Create upload directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'])
        logging.info(f"Created upload directory: {app.config['UPLOAD_FOLDER']}")
    except Exception as e:
        logging.error(f"Failed to create upload directory: {str(e)}")
        raise

# Start monitor_ttml.py as a background process
try:
    monitor_process = subprocess.Popen(["python", "monitor_ttml.py"])
    logging.info("Started monitor_ttml.py background process")
except Exception as e:
    logging.error(f"Failed to start monitor_ttml.py: {str(e)}")

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def format_timestamp(seconds):
    """Format seconds into HH:MM:SS format."""
    try:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02}:{m:02}:{s:02}"
    except Exception as e:
        logging.error(f"Error formatting timestamp {seconds}: {str(e)}")
        return "00:00:00"  # Return default on error

def extract_transcript(ttml_content, include_timestamps=False):
    """Extract transcript from TTML content."""
    try:
        root = ET.fromstring(ttml_content)
        transcript = []

        # Find all <p> elements in the TTML file
        paragraphs = root.findall(".//{http://www.w3.org/ns/ttml}p")
        logging.info(f"Found {len(paragraphs)} paragraphs in TTML content")

        for paragraph in paragraphs:
            paragraph_text = ""
            for span in paragraph.findall(".//{http://www.w3.org/ns/ttml}span"):
                if span.text:
                    paragraph_text += span.text.strip() + " "

            paragraph_text = paragraph_text.strip()
            if paragraph_text:
                if include_timestamps and "begin" in paragraph.attrib:
                    try:
                        timestamp = format_timestamp(float(paragraph.attrib["begin"].replace("s", "")))
                        transcript.append(f"[{timestamp}] {paragraph_text}")
                    except ValueError:
                        logging.warning(f"Invalid timestamp format: {paragraph.attrib['begin']}")
                        transcript.append(paragraph_text)
                else:
                    transcript.append(paragraph_text)

        result = "\n\n".join(transcript)
        logging.info(f"Successfully extracted transcript with {len(transcript)} segments")
        return result

    except ET.ParseError as e:
        error_msg = f"Error parsing TTML file: {e}"
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Unexpected error extracting transcript: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        return f"Error processing transcript: {str(e)}"

def summarize_transcript(transcript):
    """Summarize transcript using OpenAI API with chunking and retry logic."""
    logging.info(f"Starting transcript summarization (length: {len(transcript)} characters)")

    # Use fewer, larger chunks with a more efficient strategy
    max_chunk_size = 4000  # Larger chunks mean fewer API calls
    transcript_chunks = [transcript[i:i + max_chunk_size] for i in range(0, len(transcript), max_chunk_size)]
    logging.info(f"Split transcript into {len(transcript_chunks)} chunks")

    # Add a delay between initial requests to avoid hitting rate limits immediately
    summaries = []

    for i, chunk in enumerate(transcript_chunks):
        chunk_start_time = time.time()
        logging.info(f"Processing chunk {i+1}/{len(transcript_chunks)} (size: {len(chunk)} characters)")

        # Add initial delay between chunks to avoid immediate rate limiting
        if i > 0:
            time.sleep(3)  # Wait 3 seconds between initial requests

        retry_count = 0
        max_retries = 8  # Increase max retries
        success = False

        while retry_count < max_retries and not success:
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Consider using a model with higher rate limits
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes podcast transcripts."},
                        {"role": "user", "content": f"Summarize the following podcast transcript in bullet points:\n\n{chunk}"}
                    ],
                    max_tokens=300
                )
                summary_text = response.choices[0].message.content.strip()
                summaries.append(summary_text)
                success = True
                logging.info(f"Successfully summarized chunk {i+1} (took {time.time() - chunk_start_time:.2f}s)")
            except RateLimitError as e:
                retry_count += 1
                wait_time = min(60, 2 ** retry_count)  # Cap at 60 seconds max wait
                logging.warning(f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                error_msg = f"Error summarizing chunk {i+1}: {str(e)}"
                logging.error(error_msg)
                logging.error(traceback.format_exc())
                break

        # If we've exhausted retries, add a placeholder
        if not success:
            error_msg = f"Failed to summarize chunk {i+1} after {max_retries} attempts"
            logging.error(error_msg)
            summaries.append("*[This section could not be summarized due to API limitations]*")

    result = "\n\n".join(summaries)
    logging.info(f"Completed transcript summarization with {len(summaries)} summary sections")
    return result

@app.route('/')
def index():
    """Render the main page."""
    logging.info("Accessed main page")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload from web interface."""
    logging.info("File upload initiated")

    # Check if file part exists in request
    if 'file' not in request.files:
        logging.warning("No file part in request")
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']

    # Check if filename is empty
    if file.filename == '':
        logging.warning("Empty filename submitted")
        flash('No selected file')
        return redirect(request.url)

    # Process valid file
    if file and allowed_file(file.filename):
        try:
            # Save file
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logging.info(f"File saved: {file_path}")

            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                ttml_content = f.read()

            # Process file
            include_timestamps = 'timestamps' in request.form
            logging.info(f"Processing file with timestamps: {include_timestamps}")

            # Extract and summarize transcript
            transcript = extract_transcript(ttml_content, include_timestamps)
            summary = summarize_transcript(transcript)

            logging.info(f"Successfully processed file: {filename}")
            return render_template('result.html', transcript=summary)

        except Exception as e:
            error_msg = f"Error processing file {file.filename}: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            flash(f'Error processing file: {str(e)}')
            return redirect(request.url)
    else:
        logging.warning(f"Invalid file type: {file.filename}")
        flash('Invalid file type')
        return redirect(request.url)

@app.route('/upload_api', methods=['POST'])
def upload_api():
    """Handle file upload from API."""
    logging.info("API upload initiated")

    # Check if file part exists in request
    if 'file' not in request.files:
        logging.warning("API request missing file part")
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    # Check if filename is empty
    if file.filename == '':
        logging.warning("API request with empty filename")
        return jsonify({"error": "No selected file"}), 400

    # Process valid file
    if file and allowed_file(file.filename):
        try:
            # Save file
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logging.info(f"API file saved: {file_path}")

            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                ttml_content = f.read()

            # Process file
            transcript = extract_transcript(ttml_content)
            summary = summarize_transcript(transcript)

            logging.info(f"API successfully processed file: {filename}")
            return jsonify({"summary": summary})

        except Exception as e:
            error_msg = f"API error processing file {file.filename}: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            return jsonify({"error": str(e)}), 500
    else:
        logging.warning(f"API invalid file type: {file.filename}")
        return jsonify({"error": "Invalid file type"}), 400

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error."""
    logging.warning("File upload too large")
    return jsonify({"error": "File too large"}), 413

@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors."""
    logging.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

@app.route('/health')
def health_check():
    """Simple health check endpoint."""
    try:
        # Check OpenAI API
        client.models.list()
        api_status = "ok"
    except Exception as e:
        logging.error(f"Health check - OpenAI API error: {str(e)}")
        api_status = "error"

    return jsonify({
        "status": "ok" if api_status == "ok" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "openai_api": api_status
        }
    })

if __name__ == "__main__":
    logging.info("Starting Flask application")
    app.run(debug=True)