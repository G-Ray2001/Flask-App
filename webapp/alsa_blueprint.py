from flask import Blueprint, render_template, request, jsonify

alsa_bp = Blueprint('alsa', __name__)

@alsa_bp.route('/alsa_settings', methods=['GET', 'POST'])
def alsa_settings():
    if request.method == 'POST':
        # Mock applying settings
        numid = request.form.get('numid')
        value = request.form.get('value')
        print(f"Set numid {numid} to value {value}")
        return jsonify({'status': 'success', 'numid': numid, 'value': value})

    # Mock mixer settings
    mixer_settings = [
        {'numid': '1', 'name': 'Master Volume', 'value': '50%', 'type': 'integer'},
        {'numid': '2', 'name': 'Capture Gain', 'value': '30%', 'type': 'integer'}
    ]
    return render_template('alsa_settings.html', mixer_settings=mixer_settings)
