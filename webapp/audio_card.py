from flask import Blueprint, Response, request, jsonify
import json

# Create a Blueprint for audio card-related routes
audio_card_bp = Blueprint('audio_card', __name__)

# Utility function to load the primary card
def load_primary_card():
    with open('primary_card.json', 'r') as file:
        return json.load(file).get('card_id')

# Route to set the primary card
@audio_card_bp.route('/set_primary_card', methods=['POST'])
def set_primary_card():
    card_id = request.json.get('card_id')
    if card_id:
        with open('primary_card.json', 'w') as file:
            json.dump({'card_id': card_id}, file)
        return Response("Primary card updated successfully!", status=200)
    return Response("Card ID not provided", status=400)


# Route to fetch controls for the primary card
@audio_card_bp.route('/controls/primary')
def get_primary_controls():
    primary_card = load_primary_card()
    # Assuming you have a function to get all controls (e.g., from ALSA Mixer)
    all_controls = get_all_controls()
    filtered_controls = [
        control for control in all_controls
        if control['card_id'] == primary_card and control['type'] in ['INPUT_CAPTURE', 'VOLUME']
    ]
    return jsonify(filtered_controls)

@audio_card_bp.route('/test', methods=['GET'])
def test():
    return "Blueprint route is working!"
