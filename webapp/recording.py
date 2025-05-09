import subprocess
import os
from datetime import datetime

RECORDINGS_DIR = "/home/pi/webapp/recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

def generate_filename():
    base_filename = datetime.now().strftime("Rec._%m_%d_%y")
    counter = 1
    filename = f"{counter}_{base_filename}.mp3"
    while os.path.exists(os.path.join(RECORDINGS_DIR, filename)):
        counter += 1
        filename = f"{counter}_{base_filename}.mp3"
    return filename

def write_metadata(filepath):
    metadata = load_metadata()
    temp_filepath = f"{filepath}.temp.mp3"
    album_art_path = '/home/pi/webapp/albumart.jpg'

    command = [
        "ffmpeg", "-y", "-i", filepath,
        "-i", album_art_path,
        "-map", "0", "-map", "1",
        "-metadata", f"title={metadata.get('title', '')}",
        "-metadata", f"artist={metadata.get('artist', '')}",
        "-metadata", f"album={metadata.get('album', '')}",
        "-metadata", f"genre={metadata.get('genre', '')}",
        "-metadata", f"year={metadata.get('year', '')}",
        "-metadata", f"comment={metadata.get('comments', '')}",
        "-disposition:v:0", "attached_pic",
        "-c", "copy", temp_filepath
    ]

    subprocess.run(command, check=True)
    os.replace(temp_filepath, filepath)
