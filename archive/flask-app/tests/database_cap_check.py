import shutil
import os

def get_database_size(db_path):
    return os.path.getsize(db_path)

def get_available_disk_space(db_path):
    total, used, free = shutil.disk_usage(os.path.dirname(db_path))
    return free

def is_database_full(db_path):
    db_size = get_database_size(db_path)
    print("DB Size: ", db_size)
    available_space = get_available_disk_space(db_path)
    print("Available Space: ", available_space)
    # Check if the database size is greater than or equal to the available space
    if db_size >= available_space:
        return True
    return False

# Example usage
db_path = '/Users/saikamat/Documents/Python Scripts/apple-podcast-transcript-extractor/podcast_transcripts.db'
if is_database_full(db_path):
    print("The database is full.")
else:
    print("The database is not full.")

