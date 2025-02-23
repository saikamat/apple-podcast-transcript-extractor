from flask import Flask, render_template, send_from_directory
import os

app = Flask(__name__)

# Path to the folder containing transcripts and summaries
TRANSCRIPTS_DIR = "./transcripts"

@app.route("/")
def index():
    """
    List all transcript and summary files in the transcripts directory.
    """
    files = []
    for root, _, filenames in os.walk(TRANSCRIPTS_DIR):
        for filename in filenames:
            files.append(os.path.relpath(os.path.join(root, filename), TRANSCRIPTS_DIR))
    return render_template("index.html", files=files)

@app.route("/transcripts/<path:filename")
def download_file(filename):
    """
    Serve a specific transcript or summary file for download or viewing.
    """
    return send_from_directory(TRANSCRIPTS_DIR, filename)

if __name__ == "__main__":
    app.run(debug=True)