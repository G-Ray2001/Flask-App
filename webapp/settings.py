import os
import json

METADATA_FILE = 'metadata.json'
ALBUM_ART_PATH = '/home/pi/webapp/albumart.jpg'

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    else:
        return {
            'title': '',
            'artist': '',
            'album': '',
            'genre': '',
            'year': '',
            'comments': ''
        }

def save_metadata(metadata, album_art):
    # Save metadata to JSON file
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=4)

    # Save album art if provided
    if album_art:
        album_art.save(ALBUM_ART_PATH)
