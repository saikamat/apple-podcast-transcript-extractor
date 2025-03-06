import os
import subprocess
import xml.etree.ElementTree as ET
from flask import Flask, request, render_template, redirect, flash, jsonify
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import time
from openai import RateLimitError

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
# Start monitor_ttml.py as a background process
subprocess.Popen(["python", "monitor_ttml.py"])

app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'ttml'}


if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def format_timestamp(seconds):
    """Format seconds into HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"

def extract_transcript(ttml_content, include_timestamps=False):
    """Extract transcript from TTML content."""
    try:
        root = ET.fromstring(ttml_content)
        transcript = []

        # Find all <p> elements in the TTML file
        paragraphs = root.findall(".//{http://www.w3.org/ns/ttml}p")

        for paragraph in paragraphs:
            paragraph_text = ""
            for span in paragraph.findall(".//{http://www.w3.org/ns/ttml}span"):
                if span.text:
                    paragraph_text += span.text.strip() + " "

            paragraph_text = paragraph_text.strip()
            if paragraph_text:
                if include_timestamps and "begin" in paragraph.attrib:
                    timestamp = format_timestamp(float(paragraph.attrib["begin"].replace("s", "")))
                    transcript.append(f"[{timestamp}] {paragraph_text}")
                else:
                    transcript.append(paragraph_text)

        return "\n\n".join(transcript)

    except ET.ParseError as e:
        return f"Error parsing TTML file: {e}"

def summarize_transcript(transcript):
    # Use fewer, larger chunks with a more efficient strategy
    max_chunk_size = 4000  # Larger chunks mean fewer API calls
    transcript_chunks = [transcript[i:i + max_chunk_size] for i in range(0, len(transcript), max_chunk_size)]

    # Add a delay between initial requests to avoid hitting rate limits immediately
    summaries = []

    for i, chunk in enumerate(transcript_chunks):
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
                summaries.append(response.choices[0].message.content.strip())
                success = True
            except RateLimitError as e:
                retry_count += 1
                wait_time = min(60, 2 ** retry_count)  # Cap at 60 seconds max wait
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                print(f"An error occurred: {e}")
                break

        # If we've exhausted retries, add a placeholder
        if not success:
            summaries.append("*[This section could not be summarized due to API limitations]*")

    return "\n\n".join(summaries)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            ttml_content = f.read()
        include_timestamps = 'timestamps' in request.form
        transcript = extract_transcript(ttml_content, include_timestamps)
        summary = summarize_transcript(transcript)
        return render_template('result.html', transcript=summary)
    else:
        flash('Invalid file type')
        return redirect(request.url)
    
@app.route('/upload_api', methods=['POST'])
def upload_api():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            ttml_content = f.read()
        transcript = extract_transcript(ttml_content)
        summary = summarize_transcript(transcript)
        return jsonify({"summary": summary})
    else:
        return jsonify({"error": "Invalid file type"}), 400

if __name__ == "__main__":
    app.run(debug=True)