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

def send_messages(messages, tools):
    response = client.chat.completions.create(
        model="claude-haiku-4-5",
        messages=messages,
        tools=tools
    )
    return response.choices[0].message

def build_mode_json():
    input_path = "modes.txt"  # path to the text file to read

    with open(input_path, "r", encoding="utf-8") as f:
        description = f.read().strip()

    return [
        {
            "type": "function",
            "function": {
                "name": "choose_mode",
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["sys_admin", "accountant"],
                        }
                    },
                    "required": ["mode"],
                },
            },
        }
    ]

class Conductor():
    def __init__(self):
        #keyboard event listener
        self.key_listener = None
        #audio recorder and transcriber
        self.audio_converter = AudioConverter()
        #llm tool coordinator
        self.tool_runner = ToolRunner()
        self.ubix_mode = "sys_admin"

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
                mode = self.tool_runner.execute(command)


        if key == Key.delete: 
            return False

class AudioConverter():
    def __init__(self):
        self.recorder = threading.Thread(target=self.record, daemon=False)
        self.should_record = False
        self.transcriber = threading.Thread(target=self.transcribe, daemon=False)

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
        os.remove('output.wav')
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

    def execute_tool(self, tool, arguments):
        args = json.loads(arguments)
        ledger_path = "/home/will/projects/software/ubix/files/pyubix/test.journal"
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
            case "choose_mode":
                with open(ledger_path) as f:
                    return f.read()
            case _:
                return "nocommand"

    def execute(self, command):
        api_key = os.environ.get("DEEPSEEK_API_KEY")

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        with open("functions.json") as f:
            tools = json.load(f)

        with open("prompt.md") as f:
            prompt = f.read()

        mode_selection_json = build_mode_json()

        messages = [
                {"role" : "user", "content": command},
                {"role" : "system", "content": prompt}
                ]

        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages = messages,
            tools = tools
        )

        message = send_messages(messages, tools)

        #here we are adding the tool_calls evidence?
        messages.append(message)
        print(f'System> {message.content}')
        while(message.tool_calls):
            tool = response.choices[0].message.tool_calls[0]
            tool_name = tool.function.name
            tool_id = tool.id
            tool_args = tool.function.arguments

            result = self.execute_tool(tool_name, tool_args)
            #add tool call result to messages history
            message = {"role" : "tool", "tool_call_id": tool_id, "content" : result}
            messages.append(message)
            #send new history to model
            message = send_messages(messages, tools)
            messages.append(message)
        print(f'System> {message.content}')
        return self.mode



conductor = Conductor()

print("Welcome to Ubix!")

conductor.start_listener()
conductor.listener.join()  # block main thread until listener stops so the interpreter doesn't enter shutdown while work is in flight



