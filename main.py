import os
import sys
import threading
from pynput import keyboard
import pyaudio
import speech_recognition as sr
import wave
import openai
import textwrap
from queue import Queue, Empty

event_queue = Queue()

# Replace 'your_api_key_here' with your actual API key
openai.api_key = ""


def chat_gpt(prompt, model="text-curie-001", tokens=500, temperature=0.1):
    response = openai.Completion.create(
        engine=model,
        prompt=prompt,
        max_tokens=tokens,
        n=1,
        stop=None,
        temperature=temperature,
    )
    return response.choices[0].text.strip()


# Initialize the recognizer
recognizer = sr.Recognizer()

# Configure the recording settings
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK = 1024

# Initialize PyAudio
audio = pyaudio.PyAudio()

loopback_device = None
for i in range(audio.get_device_count()):
    device_info = audio.get_device_info_by_index(i)
    if "Loopback" in device_info["name"] or "Stereo Mix" in device_info["name"]:
        loopback_device = device_info
        break

if not loopback_device:
    print("Loopback device not found.")
    exit()

# Open the audio stream
stream = audio.open(
    format=pyaudio.paInt16,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    frames_per_buffer=CHUNK,
    input=True,
    input_device_index=loopback_device["index"],
)


class Recorder:
    def __init__(self):
        self.frames = []
        self.recording = False
        self.stop_event = threading.Event()

    def start(self):
        print("Listening started...")
        self.frames = []
        self.recording = True
        while not self.stop_event.is_set():
            data = stream.read(CHUNK)
            self.frames.append(data)

    def stop(self):
        print("Listening stopped.")
        self.recording = False
        self.stop_event.set()


class Audioer:
    r = sr.Recognizer()

    def __init__(self):
        self.recording = False
        self.stop_event = threading.Event()

    def start(self):
        self.recording = True
        while not self.stop_event.is_set():
            with sr.Microphone() as source:
                print("Recording started. Speak something:")
                audio_data = self.r.listen(source)
                text = self.r.recognize_google(audio_data)
                print("Transcription: " + text)
                bot_response = chat_gpt(text)
                print("Bot response:")
                for line in textwrap.wrap(bot_response, width=80):
                    print(line)
                print("\n \n")
    def stop(self):
        self.recording = False
        self.stop_event.set()


recorder = Recorder()
audioer = Audioer()


def transcribe_audio():
    with wave.open("output.wav", "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(b"".join(recorder.frames))

    with sr.AudioFile("output.wav") as source:
        audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language='en')
        bot_response = chat_gpt(text)
        print("Transcription:", text)
        print("Bot response:")
        for line in textwrap.wrap(bot_response, width=80):
            print(line)
    if os.path.exists('output.wav'):
        os.remove('output.wav')


def stop_audio_stream():
    stream.stop_stream()
    stream.close()
    audio.terminate()


keep_running = True


def on_press(key):
    try:
        k = key.char
    except AttributeError:
        k = key.name

    if k in ['s', 'h', 'q', 'k']:
        event_queue.put(k)


def on_release(key):
    pass


print("Please press one of the following choices:\n\n"
      "1) Press 's' to listen to audio coming from speakers and ask the bot\n"
      "2) Press 'h' to speak into the mic to ask the bot\n"
      "3) Press 'k' to stop the application\n\n"
      "Please note, when you press the choices, you need to press 'q' when you are done recording or listening to your audio to get the results.\n\n")


def process_events():
    global event_queue
    global keep_running
    recorder_thread = None
    audioer_thread = None
    recording_obj = None
    event_queue = Queue()

    while keep_running:
        k = event_queue.get(block=True)

        if k == 's':
            if not recorder.recording:
                recorder.stop_event.clear()
                recorder_thread = threading.Thread(target=recorder.start)
                recorder_thread.start()
                recording_obj = recorder
            else:
                recorder.stop()
                recorder_thread.join()
                transcribe_audio()
                recording_obj = None

        elif k == 'h':
            if not audioer.recording:
                audioer.stop_event.clear()
                audioer_thread = threading.Thread(target=audioer.start)
                audioer_thread.start()
                recording_obj = audioer
            else:
                audioer.stop()
                audioer_thread.join()
                recording_obj = None

        elif k == 'q':
            if recording_obj and recording_obj.recording:
                recording_obj.stop()
                recording_obj.recording = False
                recording_obj.stop_event.set()
                recording_obj_thread = audioer_thread if recording_obj == audioer else recorder_thread
                recording_obj_thread.join()
                if isinstance(recording_obj, Recorder):
                    transcribe_audio()
                print("Please make another selection - choose S, H or K")

        elif k == 'k':
            keep_running = False


with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    process_events()
listener.join()

while keep_running:
    pass
