import os
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
import hashlib
import json
from functools import lru_cache
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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

# Set up cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
if not os.path.exists(CACHE_DIR):
    try:
        os.makedirs(CACHE_DIR)
        logging.info(f"Created cache directory: {CACHE_DIR}")
    except Exception as e:
        logging.error(f"Failed to create cache directory: {str(e)}")
        raise

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

# Caching functions
def get_file_hash(content):
    """Generate a unique hash for file content."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def get_cache_path(file_hash):
    """Get the path to the cache file for a given hash."""
    return os.path.join(CACHE_DIR, f"{file_hash}.json")

def save_to_cache(file_hash, transcript, summary, include_timestamps=False):
    """Save processing results to cache."""
    try:
        cache_data = {
            'transcript': transcript,
            'summary': summary,
            'timestamp': time.time(),
            'include_timestamps': include_timestamps
        }

        with open(get_cache_path(file_hash), 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)

        logging.info(f"Saved results to cache for hash: {file_hash}")
        return True
    except Exception as e:
        logging.error(f"Failed to save to cache: {str(e)}")
        return False

def get_from_cache(file_hash):
    """Retrieve processing results from cache if available."""
    cache_path = get_cache_path(file_hash)

    if not os.path.exists(cache_path):
        logging.info(f"No cache found for hash: {file_hash}")
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        # Optional: Check if cache is too old (e.g., older than 30 days)
        cache_age = time.time() - cache_data.get('timestamp', 0)
        if cache_age > 30 * 24 * 60 * 60:  # 30 days in seconds
            logging.info(f"Cache expired for hash: {file_hash}")
            return None

        logging.info(f"Retrieved results from cache for hash: {file_hash}")
        return cache_data
    except Exception as e:
        logging.error(f"Failed to read from cache: {str(e)}")
        return None

# Memory-based cache for frequently accessed results
@lru_cache(maxsize=50)
def get_cached_summary_memory(file_hash):
    """In-memory cache for the most recently accessed summaries."""
    cache_data = get_from_cache(file_hash)
    if cache_data:
        return cache_data.get('summary')
    return None

# File watcher for the uploads directory
class UploadsHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".ttml"):
            logging.info(f"New file detected in uploads: {event.src_path}")
            self.process_file(event.src_path)

    def process_file(self, file_path):
        try:
            filename = os.path.basename(file_path)
            logging.info(f"Processing file: {filename}")

            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                ttml_content = f.read()

            # Generate hash for caching
            file_hash = get_file_hash(ttml_content)
            logging.info(f"File hash: {file_hash}")

            # Check if already processed (default without timestamps)
            cached_data = get_from_cache(file_hash)
            if cached_data:
                logging.info(f"File already processed: {filename}")
                return

            # Process file
            include_timestamps = False  # Default setting
            transcript = extract_transcript(ttml_content, include_timestamps)
            summary = summarize_transcript(transcript)

            # Save to cache
            save_to_cache(file_hash, transcript, summary, include_timestamps)

            logging.info(f"Successfully processed file: {filename}")
        except Exception as e:
            error_msg = f"Error processing file {file_path}: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())

@app.route('/')
def index():
    """Render the main page."""
    logging.info("Accessed main page")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload from web interface with caching."""
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

            # Get user preferences
            include_timestamps = 'timestamps' in request.form

            # Generate hash for caching
            file_hash = get_file_hash(ttml_content)
            logging.info(f"File hash: {file_hash}")

            # Check cache first
            cached_data = get_from_cache(file_hash)
            if cached_data:
                logging.info(f"Using cached results for {filename}")

                # Check if the cached version matches the timestamp preference
                cached_timestamps = cached_data.get('include_timestamps', False)

                if include_timestamps == cached_timestamps:
                    summary = cached_data.get('summary')
                    return render_template('result.html', transcript=summary, from_cache=True)
                else:
                    logging.info(f"Timestamp preference differs from cache, reprocessing")

            # Process file if not in cache or timestamps setting differs
            logging.info(f"Processing file with timestamps: {include_timestamps}")

            # Extract and summarize transcript
            transcript = extract_transcript(ttml_content, include_timestamps)
            summary = summarize_transcript(transcript)

            # Save to cache
            save_to_cache(file_hash, transcript, summary, include_timestamps)

            logging.info(f"Successfully processed file: {filename}")
            return render_template('result.html', transcript=summary, from_cache=False)

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

@app.route('/cache/stats', methods=['GET'])
def cache_stats():
    """View cache statistics."""
    try:
        if not os.path.exists(CACHE_DIR):
            return jsonify({"error": "Cache directory does not exist"}), 404

        cache_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
        total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in cache_files)

        stats = {
            "cache_entries": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_directory": CACHE_DIR
        }

        logging.info(f"Cache stats: {len(cache_files)} entries, {stats['total_size_mb']} MB")
        return jsonify(stats)
    except Exception as e:
        logging.error(f"Error getting cache stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear the cache."""
    try:
        if not os.path.exists(CACHE_DIR):
            return jsonify({"error": "Cache directory does not exist"}), 404

        cache_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
        for file in cache_files:
            os.remove(os.path.join(CACHE_DIR, file))

        # Also clear the in-memory cache
        get_cached_summary_memory.cache_clear()

        logging.info(f"Cleared {len(cache_files)} cache entries")
        return jsonify({"message": f"Cleared {len(cache_files)} cache entries"})
    except Exception as e:
        logging.error(f"Error clearing cache: {str(e)}")
        return jsonify({"error": str(e)}), 500

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

    # Check cache directory
    cache_status = "ok" if os.path.exists(CACHE_DIR) else "error"

    return jsonify({
        "status": "ok" if api_status == "ok" and cache_status == "ok" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "openai_api": api_status,
            "cache": cache_status
        }
    })

if __name__ == "__main__":
    # Start the file watcher for the uploads directory
    event_handler = UploadsHandler()
    observer = Observer()
    observer.schedule(event_handler, app.config['UPLOAD_FOLDER'], recursive=False)
    observer.start()
    logging.info(f"Started file watcher for directory: {app.config['UPLOAD_FOLDER']}")

    try:
        logging.info("Starting Flask application")
        app.run(debug=True)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()