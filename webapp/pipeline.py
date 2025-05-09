import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# GStreamer Initialization (ensure it runs once)
Gst.init(None)

audio_levels = {"rms": 0, "peak": 0}

def on_message(bus, message):
    global audio_levels
    if message.type == Gst.MessageType.ELEMENT:
        structure = message.get_structure()
        if structure and structure.has_name("level"):
            rms = structure.get_value("rms")
            peak = structure.get_value("peak")
            if isinstance(rms, (list, tuple)) and isinstance(peak, (list, tuple)):
                audio_levels["rms"] = sum(rms) / len(rms)
                audio_levels["peak"] = sum(peak) / len(peak)

def start_pipeline():
    global pipeline, loop
    Gst.init(None)
    pipeline = Gst.parse_launch("alsasrc device=plughw:2,0 ! level interval=100000000 ! fakesink")
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)
    threading.Thread(target=run_pipeline, daemon=True).start()

def stop_pipeline():
    global pipeline, loop
    if pipeline:
        pipeline.set_state(Gst.State.NULL)
    if loop:
        loop.quit()
    pipeline, loop = None, None
