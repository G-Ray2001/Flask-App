# app.py
from flask import Flask, render_template, send_from_directory, redirect, url_for, jsonify, request
import os
import subprocess
import json
import time
from datetime import datetime
from mutagen.mp3 import MP3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading
#from flask import Flask, jsonify, render_template
#import gi
#gi.require_version('Gst', '1.0')
#from gi.repository import Gst, GLib
#import threading

app = Flask(__name__)

# Initialize GStreamer
Gst.init(None)
pipeline = Gst.parse_launch("alsasrc device=plughw:2,0 ! level interval=100000000 ! fakesink")
bus = pipeline.get_bus()
bus.add_signal_watch()

# Shared variables for storing audio levels
audio_levels = {"rms": 0, "peak": 0}

def on_message(bus, message):
    global audio_levels
    if message.type == Gst.MessageType.ELEMENT:
        structure = message.get_structure()
        if structure and structure.has_name("level"):
            audio_levels["rms"] = structure.get_value("rms")[0]
            audio_levels["peak"] = structure.get_value("peak")[0]

bus.connect("message", on_message)

# Run GStreamer pipeline in a separate thread
def run_pipeline():
    pipeline.set_state(Gst.State.PLAYING)
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pipeline.set_state(Gst.State.NULL)

threading.Thread(target=run_pipeline, daemon=True).start()

# Run the shell script to adjust mixer settings on startup
subprocess.run(['./mixersettings.sh'], check=True)

monitoring_process = None
alsaloop_process = None  # Declare global variable to track alsaloop
RECORDINGS_DIR = "/home/pi/webapp/recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

ffmpeg_process = None
start_time = None  # Initialize start_time globally

# Function to load metadata from JSON
def load_metadata():
    metadata_file = 'metadata.json'
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            return json.load(f)
    return {}

# Function to add metadata to MP3 file
def write_metadata(filepath):
    metadata = load_metadata()
    temp_filepath = f"{filepath}.temp.mp3"
    album_art_path = '/home/pi/webapp/albumart.jpg'

    command = [
        "ffmpeg", "-y", "-i", filepath,
        "-i", album_art_path,  # Attach album art
        "-map", "0", "-map", "1",  # Map the audio and image streams
        "-metadata", f"title={metadata.get('title', '')}",
        "-metadata", f"artist={metadata.get('artist', '')}",
        "-metadata", f"album={metadata.get('album', '')}",
        "-metadata", f"genre={metadata.get('genre', '')}",
        "-metadata", f"year={metadata.get('year', '')}",
        "-metadata", f"comment={metadata.get('comments', '')}",
        "-disposition:v:0", "attached_pic",  # Mark the image as album art
        "-c", "copy", temp_filepath  # Copy streams without re-encoding
    ]

    try:
        print(f"Running FFmpeg command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(f"FFmpeg completed successfully: {result.stdout}")
        os.replace(temp_filepath, filepath)  # Replace the original file with the updated file
        print(f"Metadata successfully written to {filepath}")
    except subprocess.CalledProcessError as e:
        print(f"Error running FFmpeg: {e.stderr}")
    except Exception as ex:
        print(f"Error replacing the file: {ex}")

def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{int(hours)}H {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

@app.route('/current_time')
def current_time():
    now = datetime.now()
    formatted_time = now.strftime("%A, %B %d, %Y %I:%M:%S %p")
    return jsonify({'current_time': formatted_time})

def generate_filename():
    base_filename = datetime.now().strftime("Rec._%m_%d_%y")
    counter = 1
    filename = f"{counter}_{base_filename}.mp3"
    while os.path.exists(os.path.join(RECORDINGS_DIR, filename)):
        counter += 1
        filename = f"{counter}_{base_filename}.mp3"
    return filename

# Function to get memory info with only total, used, and free memory
def get_memory_info():
    # Run the `free -h` command
    memory_info = subprocess.run(['free', '-h'], stdout=subprocess.PIPE, text=True).stdout
    
    # Split lines and columns to access only relevant parts
    lines = memory_info.splitlines()
    
    # Find the memory line (e.g., the second line in output)
    mem_line = lines[1].split()
    
    # Extract total, used, and free memory values
    memory_data = {
        "Total": mem_line[1],
        "Used": mem_line[2],
        "Free": mem_line[3]
    }
    
    return memory_data
def verify_audio_settings(): 
    """Check if 'Line' capture is enabled, and apply settings if needed."""
    check = subprocess.run(["amixer", "-c", "2", "get", "Line"], capture_output=True, text=True)
    
    if "Capture [on]" not in check.stdout:
        print("Line capture is OFF. Applying settings...")
        subprocess.run(["amixer", "-c", "2", "sset", "Line", "cap"], check=True)
        subprocess.run(["amixer", "-c", "2", "sset", "Mic", "nocap"], check=False)
        subprocess.run(["amixer", "-c", "2", "sset", "Master", "0.0dB", "0.0dB"], check=True)
    else:
        print("Line capture is ON. No changes needed.")

def is_recording(): # routine to check and see if a recording is in progress
    result = subprocess.run(["pgrep", "-f", "gst-launch-1.0"], capture_output=True, text=True)
    return result.stdout.strip() != ""  # Returns True if recording is in progress, False otherwise
 
@app.route('/')
def index():
    # Get all .mp3 files in the directory with their modification times
    files = [
        f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.mp3')
    ]
    # Sort files by modification time (newest first)
    files = sorted(
        files, 
        key=lambda f: os.path.getmtime(os.path.join(RECORDINGS_DIR, f)), 
        reverse=True
    )

    # Check if recording is in progress and calculate elapsed time if so
    recording_in_progress = ffmpeg_process is not None
    elapsed_time = 0
    if recording_in_progress and start_time:
        elapsed_time = int((datetime.now() - start_time).total_seconds())

    return render_template('index.html', files=files, recording_in_progress=recording_in_progress, elapsed_time=elapsed_time) 

@app.route('/start_recording')
def start_recording():
    
    # Verify and apply alsamixer settings if necessary
    verify_audio_settings()
    
    global ffmpeg_process, start_time
    if ffmpeg_process is not None:
        return redirect(url_for('index'))
    
    metadata = load_metadata()
    filename = generate_filename()
    filepath = os.path.join(RECORDINGS_DIR, filename)
    start_time = datetime.now()  # Set the start time when recording begins
    
    # Use GStreamer to record audio and save it to a file (e.g., .mp3 format)
    ffmpeg_process = subprocess.Popen([
        "gst-launch-1.0",  # GStreamer command
        "alsasrc",
        "device=hw:2,0",  # Use the ALSA source for audio input (adjust the device name if necessary)
        "!",
        "audioresample",  # Resample if needed
        "!",
        "lamemp3enc",  # You can replace this with other encoders like mp3 or wavenc
        "!",
        "filesink",  # Output to file
        f"location={filepath}"  # Specify the output file location
    ])
    
    return redirect(url_for('index'))

@app.route('/is_recording') # Invokes the recording test
def check_recording_status():
    return jsonify({'recording': is_recording()})

    
@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global ffmpeg_process, start_time
    if ffmpeg_process:
        ffmpeg_process.terminate()
        ffmpeg_process = None
        start_time = None

        # Add metadata to the latest recording
        try:
            mp3_files = [
                os.path.join(RECORDINGS_DIR, f) for f in os.listdir(RECORDINGS_DIR) if f.endswith(".mp3")
            ]
            if mp3_files:
                latest_file = max(mp3_files, key=os.path.getmtime)
                print(f"Latest MP3 file found: {latest_file}")
                write_metadata(latest_file)
            else:
                print("No MP3 files found in the recordings directory.")
        except Exception as e:
            print(f"Error writing metadata: {e}")

    return redirect(url_for('index'))

@app.route('/manage')
def manage_recordings():
    # Get all MP3 files in the recordings directory
    mp3_files = [
        os.path.join(RECORDINGS_DIR, f) for f in os.listdir(RECORDINGS_DIR) if f.endswith('.mp3')
    ]
    
    # Check if the directory is empty
    if not mp3_files:
        return render_template('manage.html', files=[], empty=True)

    # Populate files with metadata if not empty
    files = []
    for file_path in sorted(mp3_files, key=os.path.getmtime, reverse=True):
        filename = os.path.basename(file_path)
        try:
            audio = MP3(file_path)
            duration = audio.info.length
            file_info = {
                'name': filename,
                'length': format_duration(duration),
                'size': round(os.path.getsize(file_path) / 1024, 2),
                'date': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%m-%d-%Y %H:%M:%S')
            }
        except Exception as e:
            print(f"Error retrieving metadata for {filename}: {e}")
            file_info = {
                'name': filename,
                'date': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%m-%d-%Y %H:%M:%S')
            }
        files.append(file_info)

    # Pass the populated files list and empty=False to the template
    return render_template('manage.html', files=files, empty=False)


@app.route('/recordings/<filename>')
def download_file(filename):
    return send_from_directory(RECORDINGS_DIR, filename, as_attachment=True)


def format_time(seconds):
    minutes = int(seconds) // 60
    seconds = int(seconds) % 60
    return f"{minutes}:{seconds:02}"
   
@app.route('/rename/<filename>', methods=['POST'])
def rename_recording(filename):
    old_file_path = os.path.join(RECORDINGS_DIR, filename)
    new_name = request.form.get("new_name")
    new_file_path = os.path.join(RECORDINGS_DIR, f"{new_name}.mp3")

    # Check if the new file name already exists
    if os.path.exists(new_file_path):
        return redirect(url_for('manage_recordings'))

    # Rename the file
    os.rename(old_file_path, new_file_path)
    return redirect(url_for('manage_recordings'))


@app.route('/delete/<filename>', methods=['POST'])
def delete_recording(filename):
    try:
        file_path = os.path.join(RECORDINGS_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        return redirect(url_for('manage_recordings'))
    except Exception as e:
        print(f"Error deleting file {filename}: {e}")
        return redirect(url_for('manage_recordings'))

@app.route('/delete_all_recordings', methods=['POST'])
def delete_all_recordings():
    try:
        for filename in os.listdir(RECORDINGS_DIR):
            file_path = os.path.join(RECORDINGS_DIR, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        return redirect(url_for('manage_recordings'))
    except Exception as e:
        print(f"Error deleting all recordings: {e}")
        return redirect(url_for('manage_recordings'))

        


@app.route('/update_duration')
def update_duration():
    if start_time:
        elapsed_time = int((datetime.now() - start_time).total_seconds())
    else:
        elapsed_time = 0
    minutes = elapsed_time // 60
    seconds = elapsed_time % 60
    return jsonify(minutes=minutes, seconds=seconds)
 

    
# Function to get CPU stats from /proc/stat
def get_cpu_usage():
    with open('/proc/stat', 'r') as f:
        lines = f.readlines()

    cpu_line = lines[0]  # The first line contains CPU stats
    cpu_stats = cpu_line.split()[1:]  # Skip the "cpu" prefix

    # Convert string values to integers
    cpu_stats = list(map(int, cpu_stats))

    # The CPU usage fields:
    user, nice, system, idle, iowait, irq, softirq, steal = cpu_stats[:8]
    total_idle = idle + iowait
    total_usage = user + nice + system + irq + softirq + steal
    total = total_idle + total_usage

    return total_idle, total

# Function to calculate CPU usage percentage
def calculate_cpu_percentage():
    idle_1, total_1 = get_cpu_usage()
    time.sleep(1)  # Wait a second
    idle_2, total_2 = get_cpu_usage()

    idle_delta = idle_2 - idle_1
    total_delta = total_2 - total_1

    # Calculate CPU usage percentage
    cpu_percentage = 100 * (1 - idle_delta / total_delta)

    return cpu_percentage

# Flask route for diagnostics page
@app.route('/diagnostics')
def diagnostics():
    uptime = subprocess.run(['uptime', '-p'], stdout=subprocess.PIPE, text=True).stdout.strip()
    temp = subprocess.run(['vcgencmd', 'measure_temp'], stdout=subprocess.PIPE, text=True).stdout.strip()
    cpu_percent = calculate_cpu_percentage()  # Use the new CPU usage method
    memory_data = get_memory_info()
    disk_usage = subprocess.run(['df', '-h', '/'], stdout=subprocess.PIPE, text=True).stdout

    return render_template('diagnostics.html', 
                            uptime=uptime, 
                            temp=temp, 
                            cpu_percent=f"{cpu_percent:.2f}",  # Format to 2 decimal places
                            memory_data=memory_data, 
                            disk_usage=disk_usage)

# Route to set system date and time
@app.route('/set_datetime', methods=['POST'])
def set_datetime():
    date = request.form['date']  # Format: YYYY-MM-DD
    time = request.form['time']  # Format: HH:MM

    datetime_str = f"{date} {time}"
    try:
        subprocess.run(['sudo', 'date', '-s', datetime_str], check=True)
        subprocess.run(['sudo', 'hwclock', '-w'], check=True)  # Sync to RTC
    except subprocess.CalledProcessError as e:
        print("Error setting date and time:", e)
    
    return redirect(url_for('diagnostics'))
    
# Power off the Raspberry Pi
@app.route('/power_off', methods=['POST'])
def power_off():
    subprocess.run(['sudo', 'poweroff'])
    return redirect(url_for('index'))

# Restart the Flask app service using a shell script
@app.route('/restart_app', methods=['POST'])
def restart_app():
    # Run the script asynchronously
    subprocess.Popen('bash /home/pi/webapp/restart_flask.sh', shell=True)
    return redirect(url_for('index'))

@app.route('/reboot_system', methods=['POST'])
def reboot_system():
    os.system('sudo reboot')
    return redirect(url_for('diagnostics'))  # Redirect to the diagnostics page after initiating reboot
    
# Route to render the settings page
@app.route('/settings')
def settings():
    # Check if metadata.json exists and read it
    metadata_file = 'metadata.json'
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    else:
        # Provide default values if the file does not exist
        metadata = {
            'title': '',
            'artist': '',
            'album': '',
            'genre': '',
            'year': '',
            'comments': ''
        }
    
    return render_template('settings.html', metadata=metadata)

@app.route('/save_metadata', methods=['POST'])
def save_metadata():
    metadata = {
        'title': request.form.get('title', ''),
        'artist': request.form.get('artist', ''),
        'album': request.form.get('album', ''),
        'genre': request.form.get('genre', ''),
        'year': request.form.get('year', ''),
        'comments': request.form.get('comments', '')
    }

    # Save metadata to JSON file
    with open('metadata.json', 'w') as f:
        json.dump(metadata, f, indent=4)

    # Handle album art upload
    album_art = request.files.get('album_art')
    if album_art:
        album_art.save('/home/pi/webapp/albumart.jpg')  # Save the uploaded image

    return redirect(url_for('settings'))


@app.route("/audiomonitor")
def audiomonitor():
    return render_template("audiomonitor.html")

@app.route("/levels")
def get_levels():
    return jsonify(audio_levels)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
