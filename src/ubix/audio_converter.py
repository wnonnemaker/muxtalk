from pywhispercpp.model import Model
from RealtimeSTT import AudioToTextRecorder
import os, sys, sysconfig
import logging
import importlib.resources

pkg_root = importlib.resources.files("ubix")

logger = logging.getLogger(__name__)

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

_nvidia_lib = os.path.join(sysconfig.get_path("purelib"), "nvidia", "cublas", "lib")
if os.path.isdir(_nvidia_lib) and _nvidia_lib not in os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["LD_LIBRARY_PATH"] = _nvidia_lib + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    os.execv(sys.executable, [sys.executable] + sys.argv)


#tiny drafts the live text while you talk; medium.en redoes the whole
#recording once you stop, and that final pass is what gets sent
FINAL_MODEL = "medium.en"
REALTIME_MODEL = "tiny"


class AudioConverter():
    def __init__(self):
        self.should_record = False
        #built once: loading medium.en takes seconds, too slow for every key press
        with noalsaerr():
            self._recorder = AudioToTextRecorder(
                model=FINAL_MODEL,
                realtime_model_type=REALTIME_MODEL,
                enable_realtime_transcription=True,
                language="en",
            )

    def start_recording(self):
        self.should_record = True
        self._recorder.start()
        logger.info("Started recording")

    def stop_recording(self):
        self.should_record = False
        self._recorder.stop()
        logger.info("Stopped recording, transcribing...")
        text = self._recorder.text()
        logger.info(f"Transcription: {text}")
        return text

    def shutdown(self):
        self._recorder.shutdown()
