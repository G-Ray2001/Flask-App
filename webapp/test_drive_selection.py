from flask import Flask, render_template, request, jsonify
import json

app = Flask(__name__)

# Mock function to load audio devices
def load_audio_device_mapping():
    return [
        {
            "card": "2",
            "card_name": "audioinjectorpi [audioinjector-pi-soundcard]",
            "device": "0",
            "device_name": "AudioInjector audio wm8731-hifi-0"
        }
    ]

@app.route('/select_device', methods=['GET', 'POST'])
def select_device():
    devices = load_audio_device_mapping()

    if request.method == 'POST':
        selected_card = request.form.get('selected_card')
        selected_device = request.form.get('selected_device')

        # Mock saving selection
        print(f"Selected Card: {selected_card}, Device: {selected_device}")
        return jsonify({'status': 'success', 'selected_card': selected_card, 'selected_device': selected_device})

    return render_template('select_device.html', devices=devices)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
