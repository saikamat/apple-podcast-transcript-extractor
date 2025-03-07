# monitor_ttml.py
import os
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

# Configure logging
logging.basicConfig(
    filename='monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Directory to monitor for new TTML files
SOURCE_DIR = os.path.expanduser("~/Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML")
# Directory to copy files to for processing
TARGET_DIR = "./uploads"

class TTMLHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".ttml"):
            filename = os.path.basename(event.src_path)
            target_path = os.path.join(TARGET_DIR, filename)

            try:
                # Copy file to uploads directory for app.py to process
                shutil.copy2(event.src_path, target_path)
                logging.info(f"Copied new TTML file to uploads: {filename}")
            except Exception as e:
                logging.error(f"Error copying file {filename}: {str(e)}")

if __name__ == "__main__":
    # Create target directory if it doesn't exist
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

    event_handler = TTMLHandler()
    observer = Observer()
    observer.schedule(event_handler, SOURCE_DIR, recursive=True)
    observer.start()
    logging.info(f"Monitoring directory: {SOURCE_DIR}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()