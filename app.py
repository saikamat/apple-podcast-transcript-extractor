import os
import re
import xml.etree.ElementTree as ET
from flask import Flask, request, render_template, redirect, url_for, flash
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
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
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes podcast transcripts."},
            {"role": "user", "content": f"Summarize the following podcast transcript in bullet points:\n\n{transcript}"}
        ],
        max_tokens=200
    )
    return response.choices[0].message.content.strip()

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

if __name__ == "__main__":
    app.run(debug=True)