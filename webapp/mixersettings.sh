#!/bin/bash

# Function to check if a control exists and apply a setting
apply_setting() {
    local card=$1
    local control=$2
    local params=$3

    echo "Checking for control '$control' on card $card..."

    # Get a list of controls for the card
    controls=$(amixer -c "$card" controls)

    if echo "$controls" | grep -q "$control"; then
        echo "Applying setting for $control on card $card..."
        amixer -c "$card" sset "$control" $params
    else
        echo "Control '$control' not found on card $card. Available controls are:"
        echo "$controls"
        echo "Skipping $control on card $card."
    fi
}

# Function to configure a card with all settings
configure_card() {
    local card=$1
    echo "Configuring mixer settings for card $card..."
    apply_setting "$card" "Line,0" "100%,100% unmute cap"
    apply_setting "$card" "Mic,0" "0% mute nocap"
    apply_setting "$card" "Master" "0.0dB,0.0dB"
    echo "Finished configuring card $card."
}

# Configure both cards 2 and 3
configure_card 2
configure_card 3

echo "Mixer settings applied."
