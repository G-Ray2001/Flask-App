import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

# Create a pipeline
pipeline = Gst.parse_launch("alsasrc device=plughw:2,0 ! level interval=100000000 ! fakesink")

# Bus to listen for messages
bus = pipeline.get_bus()
bus.add_signal_watch()

def on_message(bus, message):
    if message.type == Gst.MessageType.ELEMENT:
        structure = message.get_structure()
        if structure and structure.has_name("level"):
            rms_dB = structure.get_value("rms")[0]  # Extract first channel
            peak_dB = structure.get_value("peak")[0]  # Peak dB
            print(f"RMS Level: {rms_dB:.2f} dB, Peak Level: {peak_dB:.2f} dB")

# Connect message handler
bus.connect("message", on_message)

# Start the pipeline
pipeline.set_state(Gst.State.PLAYING)

# Run the main loop
loop = GLib.MainLoop()
try:
    loop.run()
except KeyboardInterrupt:
    pipeline.set_state(Gst.State.NULL)
    print("\nPipeline stopped.")
