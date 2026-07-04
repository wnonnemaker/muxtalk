#!/usr/bin/env python3 
from pynput.keyboard import Key, KeyCode, Listener
from pywhispercpp.model import Model
from openai import OpenAI
from datetime import datetime
import time
import threading
import pyaudio
import wave
import libtmux
import concurrent.futures  # add this at the top
import os
import json
import subprocess

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

class Conductor():
    def __init__(self):
        #keyboard event listener
        self.key_listener = None
        #audio recorder and transcriber
        self.audio_converter = AudioConverter()
        #llm tool coordinator
        self.tool_runner = ToolRunner()

    def start_listener(self):
        self.listener = Listener(on_press = self.on_press)
        self.listener.daemon = False
        self.listener.start()

    def on_press(self, key):
        if key == Key.ctrl_r:
            if not self.audio_converter.should_record:
                self.audio_converter.start_recording()
            else:
                #shutdown and process command
                #every line here is sequential, each will finish before running
                #next line
                self.audio_converter.stop_recording()
                command = self.audio_converter.transcribe()
                self.tool_runner.execute(command)


        if key == Key.delete: 
            return False

class AudioConverter():
    def __init__(self):
        self.recorder = threading.Thread(target=self.record, daemon=False)
        self.should_record = False
        self.transcriber = threading.Thread(target=self.transcribe, daemon=False)
        self.chatter = None

    def transcribe(self):
        model = Model('base.en')
        print("Got audio, now transcribing")
        segments = model.transcribe('output.wav')

        fulltext = ''
        for segment in segments:
            fulltext += segment.text  
        #server = libtmux.Server()
        #claude = server.sessions[3].windows[0].panes[0]
        #claude.send_keys(fulltext, enter=True)
        print(fulltext)
        return fulltext

    def record(self):
        print("Started recording")
        chunk = 1024  
        sample_format = pyaudio.paInt16  
        channels = 2
        fs = 16000  
        filename = "output.wav"

        with noalsaerr():
            p = pyaudio.PyAudio()

        stream = p.open(format=sample_format,
                        channels=channels,
                        rate=fs,
                        frames_per_buffer=chunk,
                        input=True)

        frames = []  
        while(self.should_record):
            data = stream.read(chunk)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        p.terminate()

        print('Finished recording')

        # Save the recorded data as a WAV file
        wf = wave.open(filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(fs)
        wf.writeframes(b''.join(frames))
        wf.close()
        print('recorded audio file')

    def chat(self, fulltext):
        from openai import OpenAI
        import os
        import json
        api_key = os.environ.get("DEEPSEEK_API_KEY")

        def send_messages(messages):
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=messages,
                tools=tools
            )
            return response.choices[0].message

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        with open("functions.json") as f:
            tools = json.load(f)

        messages = [{"role": "user", "content": fulltext}]
        message = send_messages(messages)
        print(f"message: \t{message}")
        print(f"User>\t {messages[0]['content']}")

        tool = message.tool_calls[0]
        args = json.loads(tool.function.arguments)
        application = args["application"]  # e.g. "brave"
        os.system(f"{application} &")
        print(f"Tool: \t{tool}")
        messages.append(message)

        message = send_messages(messages)
        print(f"Model>\t {message.content}")

    def start_recording(self):
        self.should_record = True
        self.recorder.start()

    def stop_recording(self):
        self.should_record = False
        self.recorder.join()
        self.recorder = threading.Thread(target=self.record, daemon=False)

class ToolRunner():
    def __init__(self):
        self.name = "John"

    def execute(self, command):
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        ledger_path = os.environ.get("LEDGER_FILE")

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        with open("functions.json") as f:
            tools = json.load(f)

        with open("prompt.md") as f:
            prompt = f.read()

        messages = []
        messages = [
                {"role" : "user", "content": command},
                {"role" : "system", "content": prompt}
                ]
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages = messages,
            tools = tools
        )
        #here we are adding the tool_calls evidence?
        messages.append(response.choices[0].message)
        print(f'System> {response.choices[0].message.content}')
        while(True):
            if not response.choices[0].message.tool_calls:
                print(f'System> {response.choices[0].message.content}')
                break
            tool = response.choices[0].message.tool_calls[0]
            tool_name = tool.function.name
            tool_id = tool.id
            tool_args = tool.function.arguments

            result = execute_tool(tool_name, tool_args)
            message = {"role" : "tool", "tool_call_id": tool_id, "content" : result}
            messages.append(message)
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages = messages,
                tools = tools
            )
            messages.append(response.choices[0].message)
            print("Done with second call!")

        def execute_tool(tool, arguments):
            args = json.loads(arguments)
            match tool:
                case "open_application":
                    application = args['application']
                    result = os.system(f"{application} &")
                    print(result)
                    return f"{application} opened with result {result}"
                case "display_ledger_file":
                    with open(ledger_path) as f:
                        return f.read()
                case "create_ledger_entry":
                    date = datetime.today().strftime('%Y-%m-%d')
                    ledger_entry = (
                        f"{date} {args['entry_description']}\n"
                        f"    {args['debit_account']}    {args['debit_amount']}\n"
                        f"    {args['credit_account']}    {args['credit_amount']}\n\n"
                    )
                    with open(ledger_path, "a") as f:
                        f.write(ledger_entry)
                    return f"Added entry:\n{ledger_entry}"
                case _:
                    return "nocommand"



conductor = Conductor()

print("Welcome to Ubix!")

conductor.start_listener()
conductor.listener.join()  # block main thread until listener stops so the interpreter doesn't enter shutdown while work is in flight



