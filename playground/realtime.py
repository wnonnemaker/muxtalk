#!/usr/bin/env python3
import os, sys, sysconfig
import subprocess
import threading

from pynput.keyboard import Key, Listener
from RealtimeSTT import AudioToTextRecorder

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

_nvidia_lib = os.path.join(sysconfig.get_path("purelib"), "nvidia", "cublas", "lib")
if os.path.isdir(_nvidia_lib) and _nvidia_lib not in os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["LD_LIBRARY_PATH"] = _nvidia_lib + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    with noalsaerr():
        recorder = AudioToTextRecorder()

        recording = False
        lock = threading.Lock()

        def on_release(key):
            global recording
            if key != Key.ctrl_r:
                return
            with lock:
                if not recording:
                    recording = True
                    recorder.start()
                    print("\nRecording...", flush=True)
                else:
                    recording = False
                    recorder.stop()
                    text = recorder.text()
                    if text and text.strip():
                        subprocess.run(["muxtalk", "talk", text.strip()])
                        print(f"  -> {text.strip()}")
                    print("Stopped.", flush=True)

        listener = Listener(on_release=on_release)
        listener.start()

        print("Ready. Press Right Ctrl to start/stop recording. Press Ctrl+C to quit.")

        try:
            listener.join()
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            with lock:
                if recording:
                    recording = False
                    recorder.stop()
                    text = recorder.text()
                    if text and text.strip():
                        subprocess.run(["muxtalk", "talk", text.strip()])
                        print(f"  -> {text.strip()}")
            recorder.shutdown()
