#!/usr/bin/env python3
import os, sys, sysconfig

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


def process_text(text):
    print(text)

if __name__ == "__main__":
    with noalsaerr():
        with AudioToTextRecorder(enable_realtime_transcription = True) as recorder:
            while True:
                recorder.text(process_text)
