import subprocess

def verify_audio_settings():
    check1 = subprocess.run(["amixer", "-c", "2", "get", "Line"], capture_output=True, text = True)

    if "100%" not in check1.stdout or "mute":
        print("Audio settings incorrect. Applying mixersettings.sh...")
        subprocess.run(["amixer", "-c", "2", "sset", "Line", "cap"], check=True)
        subprocess.run(["amixer", "-c", "2", "sset", "Mic", "nocap"], check=False)
        subprocess.run(["amixer", "-c", "2", "sset", "Master", "0.0dB", "0.0dB"], check=True)
    else:
        print("Audio settings are correct.")

verify_audio_settings()
