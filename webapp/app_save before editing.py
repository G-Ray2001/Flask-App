#app.py
from flask import Flask, Response, render_template, send_from_directory, redirect, url_for, jsonify, request, session
import os
import subprocess
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading
import re
import json
import time
from datetime import datetime
import logging
import psutil
from mutagen.mp3 import MP3

app = Flask(__name__)
app.debug = True  # Enable debug mode

# Ensure the logs directory exists
logs_dir = "/home/pi/webapp/logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Run the shell script to adjust mixer settings on startup
# subprocess.run(['./mixersettings.sh'], check=True)

# Directories
RECORDINGS_DIR = "/home/pi/webapp/recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

ffmpeg_process = None
start_time = None  # Initialize start_time globally

def get_selected_device():
    try:
        with open('/home/pi/webapp/selected_device.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError("Selected device file not found.")
    except json.JSONDecodeError:
        raise RuntimeError("Selected device file is corrupted.")


 # Initialize GStreamer
Gst.init(None)

# Retrieve the selected audio device
selected_device = get_selected_device()
if not selected_device:
    raise RuntimeError("No audio device selected. Please select a device before initializing the pipeline.")

# Dynamically set the ALSA source device
alsa_device = f"plughw:{selected_device['card']},{selected_device['device']}"

# Create GStreamer pipeline with the selected device
pipeline = Gst.parse_launch(f"alsasrc device={alsa_device} ! level interval=100000000 ! fakesink")
bus = pipeline.get_bus()
bus.add_signal_watch()

# Shared variables for storing audio levels
audio_levels = {"rms": 0, "peak": 0}

# Pipeline and loop initialized as global variables
pipeline = None
loop = None


# Scan audio input devices
def scan_audio_input_devices():
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        output = result.stdout
        
        devices = []
        for line in output.splitlines():
            match = re.search(r'card (\d+): ([^,]+), device (\d+): ([^\[]+)', line)
            if match:
                devices.append({
                    "card": match.group(1),
                    "card_name": match.group(2).strip(),
                    "device": match.group(3),
                    "device_name": match.group(4).strip()
                })
        return devices
    except Exception as e:
        print(f"Error scanning audio devices: {e}")
        return []
        
# Scan at startup and save devices
audio_devices = scan_audio_input_devices()
with open('/home/pi/webapp/audio_devices.json', 'w') as f:
    json.dump(audio_devices, f, indent=4)

   
    # Run the shell script to adjust mixer settings on startup
# subprocess.run(['./mixersettings.sh'], check=True)

def is_pipeline_running():
    global pipeline
    if pipeline:
        # Get the pipeline's current state
        state = pipeline.get_state(0).state
        return state == Gst.State.PLAYING
    return False
            
def on_message(bus, message):
    global audio_levels
    if message.type == Gst.MessageType.ELEMENT:
        structure = message.get_structure()
        if structure and structure.has_name("level"):
            rms = structure.get_value("rms")
            peak = structure.get_value("peak")
            print("Raw LEVEL message:", rms, peak)

            if isinstance(rms, (list, tuple)) and isinstance(peak, (list, tuple)):
                # Average across channels
                avg_rms = sum(rms) / len(rms)
                avg_peak = sum(peak) / len(peak)

                # Normalize values: map -60 dB to 0 and 0 dB to 1
                normalized_rms = max((avg_rms + 60) / 60, 0)  # Ensure values stay within 0 to 1
                normalized_peak = max((avg_peak + 60) / 60, 0)

                # Update the global audio levels
                audio_levels["rms"] = normalized_rms
                audio_levels["peak"] = normalized_peak

                # Debug normalized values
                print("Normalized audio levels:", audio_levels)
            else:
                # Handle invalid data
                audio_levels["rms"] = 0
                audio_levels["peak"] = 0
                print("Audio levels set to zero due to invalid data.")
                
@app.route('/select_device', methods=['GET', 'POST'])
def select_device():
    try:
        devices = get_audio_devices()

        # If devices is unexpectedly a Response object, convert it to a Python list
        if isinstance(devices, Response):
            devices = devices.get_json()

        if not devices:
            return "No audio devices found."

        # Default to the first device if only one is found
        if len(devices) == 1:
            selected_device = devices[0]
            with open('selected_device.json', 'w') as f:
                json.dump(selected_device, f, indent=4)
            return f"Defaulting to device: {selected_device['card_name']} ({selected_device['device_name']})"

        if request.method == 'POST':
            selected_card = request.form.get('card')
            selected_device = next((d for d in devices if d['card'] == selected_card), None)
            if selected_device:
                with open('selected_device.json', 'w') as f:
                    json.dump(selected_device, f, indent=4)
                return f"Device selected: {selected_device['card_name']} ({selected_device['device_name']})"
            else:
                return "Invalid selection."

        # Render form
        return render_template('select_device.html', devices=devices)
    except Exception as e:
        print(f"Error in /select_device route: {e}")
        return f"An error occurred: {e}", 500

               
@app.route('/set_mixer_setting', methods=['POST'])
def set_mixer_setting():
    control = request.form.get("control")
    value = request.form.get("value")
    card = request.form.get("card")

    try:
        # Apply the setting using the amixer command
        subprocess.run(["amixer", "-c", card, "sset", control, value], check=True)
        return redirect(url_for('setup'))
    except Exception as e:
        return f"Error applying mixer setting: {e}", 500


def start_pipeline():
    global pipeline, loop

    selected_device = get_selected_device()
    print(f"Selected device for pipeline: {selected_device}")  # Debugging selected device
    if not selected_device:
        raise RuntimeError("No audio device selected. Please select a device before starting the pipeline.")

    Gst.init(None)
    alsa_device = f"plughw:{selected_device['card']},{selected_device['device']}"
    print(f"Starting pipeline with ALSA device: {alsa_device}")  # Debugging ALSA device

    pipeline = Gst.parse_launch(f"alsasrc device={alsa_device} ! level interval=100000000 ! fakesink")
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)
    print("GStreamer pipeline initialized.")

    def run():
        pipeline.set_state(Gst.State.PLAYING)
        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            pipeline.set_state(Gst.State.NULL)

    threading.Thread(target=run, daemon=True).start()



def stop_pipeline():
    global pipeline, loop
    if pipeline:
        pipeline.set_state(Gst.State.NULL)
    if loop:
        loop.quit()
    pipeline = None
    loop = None
    print("GStreamer pipeline stopped.")    


# Function to load metadata from JSON
def load_metadata():
    metadata_file = '/home/pi/webapp/metadata.json'
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
    print("is_recording() result:", result.stdout.strip() != "")

@app.route('/audio_devices')
def get_audio_devices():
    return jsonify(audio_devices) 
    
@app.route('/')
def index():
    print(f"Recording in progress: {is_recording()}")
    print(f"Files in directory: {os.listdir(RECORDINGS_DIR)}")
    print("ffmpeg_process:", ffmpeg_process)
    print("start_time:", start_time)

    stop_pipeline()
    print("GStreamer pipeline stopped.")
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
    recording_in_progress = is_recording()   
    elapsed_time = 0
    if recording_in_progress and start_time:
        elapsed_time = int((datetime.now() - start_time).total_seconds())
    
    # Load selected device info
    with open('/home/pi/webapp/selected_device.json', 'r') as f:
        selected_device = json.load(f)
    
    # Extract details
    card = selected_device['card']
    device_name = selected_device['device_name'][:15]  # First 15 characters
    print(f"Rendering template with recording_in_progress={recording_in_progress}")

    # Pass details to the template
    return render_template('index.html', 
                           files=files, 
                           recording_in_progress=recording_in_progress, 
                           elapsed_time=elapsed_time, 
                           card=card, 
                           device_name=device_name)
  
@app.route('/check_session')
def check_session():
    return f"Current Recording: {session.get('current_recording')}"

@app.route('/reset_session')
def reset_session():
    session.pop("current_recording", None)
    return "Session reset!"


@app.route('/start_recording')
def start_recording():
    global ffmpeg_process, start_time
    if ffmpeg_process is not None:
        return redirect(url_for('index'))

    filename = generate_filename()  # Generate unique filename
    filepath = os.path.join(RECORDINGS_DIR, filename)
    start_time = datetime.now()  # Capture start time
    
    selected_device = get_selected_device()
    if not selected_device:
        raise RuntimeError("No audio device selected. Please select a device before starting.")

    # Store the filename in session
    session['current_recording'] = filename

    # Start recording with GStreamer
    ffmpeg_process = subprocess.Popen([
        "gst-launch-1.0",
        "alsasrc",
        f"device=plughw:{selected_device['card']},{selected_device['device']}",
        "!",
        "audioresample",
        "!",
        "lamemp3enc",
        "!",
        "filesink",
        f"location={filepath}"
    ])

    # Return filename to the frontend
    return jsonify({"recording": True, "current_recording": filename})



@app.route('/is_recording')
def is_recording():
    global ffmpeg_process
    return jsonify({
        "recording": ffmpeg_process is not None,
        "current_recording": session.get("current_recording", "")
    })

    
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

@app.route('/manage_recordings')
def manage_recordings():
    # Get all MP3 files in the recordings directory
    mp3_files = [
        os.path.join(RECORDINGS_DIR, f) for f in os.listdir(RECORDINGS_DIR) if f.endswith('.mp3')
    ]
    
    # Check if the directory is empty
    if not mp3_files:
        return render_template('manage_recordings.html', files=[], empty=True)

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
    return render_template('manage_recordings.html', files=files, empty=False)


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
        hours = elapsed_time // 3600
        minutes = (elapsed_time % 3600) // 60
        seconds = elapsed_time % 60
    else:
        hours, minutes, seconds = 0, 0, 0
    return jsonify(hours=hours, minutes=minutes, seconds=seconds)


@app.route('/alsamixer', methods=['GET', 'POST'])
def alsamixer():
    try:
        devices = get_audio_devices()

        if isinstance(devices, Response):
            devices = devices.get_json()

        if request.method == 'POST':
            selected_card = request.form.get('card')
            selected_device = next((d for d in devices if d['card'] == selected_card), None)
            if selected_device:
                with open('/home/pi/webapp/selected_device.json', 'w') as f:
                    json.dump(selected_device, f, indent=4)
                return redirect(url_for('alsamixer'))  # Reload the ALSA-Mixer page
            else:
                return "Invalid selection.", 400

        return render_template('alsamixer.html', devices=devices)
    except Exception as e:
        print(f"Error in /alsamixer route: {e}")
        return f"An error occurred: {e}", 500

@app.route("/audiomonitor")
def audiomonitor():
    global pipeline
    print("Entering /audiomonitor route")

    try:
        if not is_pipeline_running():
            print("Starting GStreamer pipeline...")
            start_pipeline()
        else:
            print("Pipeline already running. Refresh detected.")
    except RuntimeError as e:
        print(f"Pipeline error: {e}")

    try:
        selected_device = get_selected_device()
        # Limit the card_name to the first 12-14 characters
        if selected_device:
            selected_device['card_name'] = selected_device['card_name'][:14].strip()  # Shortens the name
        print(f"Selected device (shortened): {selected_device}")
    except RuntimeError as e:
        print(f"Error fetching selected device: {e}")
        selected_device = None

    print("Rendering audiomonitor.html template")
    return render_template("audiomonitor.html", selected_device=selected_device)





#@app.route("/stop_monitor")
#def stop_monitor():
    # Stop the pipeline when leaving the monitor page
#    stop_pipeline()
#    return "Pipeline stopped!"

@app.route("/levels")
def get_levels():
    return jsonify(audio_levels)

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
    metadata_file = '/home/pi/webapp/metadata.json'
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

@app.route('/setup')
def setup():
    try:
        # Dynamically determine the card to use (replace with actual logic as needed)
        audio_injector_card = "2"  # Replace with the dynamically selected card

        # Get mixer settings for the card
        mixer_settings = get_mixer_settings(audio_injector_card)
        if mixer_settings is None:
            mixer_settings = "Error retrieving mixer settings."

        return render_template('setup.html', mixer_settings=mixer_settings, card=audio_injector_card)
    except Exception as e:
        return f"Error rendering setup page: {e}", 500



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
    with open('/home/pi/webapp/metadata.json', 'w') as f:
        json.dump(metadata, f, indent=4)

    # Handle album art upload
    album_art = request.files.get('album_art')
    if album_art:
        album_art.save('/home/pi/webapp/albumart.jpg')  # Save the uploaded image

    return redirect(url_for('settings'))
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
