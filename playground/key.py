#!/usr/bin/env python3
from pynput.keyboard import Key, KeyCode, Listener

# Source - https://stackoverflow.com/a/17673011
# Posted by Nils Werner, modified by community. See post 'Timeline' for change history
# Retrieved 2026-06-25, License - CC BY-SA 4.0

from contextlib import contextmanager
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)


recording = False

def on_press(key):
    global recording
    s = KeyCode.from_char('s')
    if key == Key.ctrl_r:
        if not recording:
            print("Recording started")
            recording = True
        else:
            print("Recording ended")
            recording = False


    if key == Key.delete: 
        return False

listener = Listener(on_press = on_press)
listener.start()


def record_audio():
    import pyaudio
    import wave
    global recording

    chunk = 1024  
    sample_format = pyaudio.paInt16  
    channels = 2
    fs = 44100  
    filename = "output.wav"

    with noalsaerr():
        p = pyaudio.PyAudio()  

    stream = p.open(format=sample_format,
                    channels=channels,
                    rate=fs,
                    frames_per_buffer=chunk,
                    input=True)

    frames = []  

    # thread for data reader
    t = threading.Thread(target=crawl, args=(link,), kwargs={"delay": 2})
    while(recording):
        # This neends to loop while recording is on
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(fs)
    wf.writeframes(b''.join(frames))
    wf.close()
    print("wave file closed and maybe written")

listener.join()

