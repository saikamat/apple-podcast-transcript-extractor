import os
import time
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

UPLOAD_URL = "http://127.0.0.1:5000/upload_api"  # Flask API endpoint for uploading TTML files

class TTMLHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".ttml"):
            print(f"New TTML file detected: {event.src_path}")
            self.upload_ttml(event.src_path)

    def upload_ttml(self, file_path):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(UPLOAD_URL, files=files)
            if response.status_code == 200:
                print(f"Successfully uploaded {file_path}")
            else:
                print(f"Failed to upload {file_path}: {response.status_code}")

if __name__ == "__main__":
    ttml_dir = os.path.expanduser("~/Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML")
    event_handler = TTMLHandler()
    observer = Observer()
    observer.schedule(event_handler, ttml_dir, recursive=True)
    observer.start()
    print(f"Monitoring directory: {ttml_dir}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()