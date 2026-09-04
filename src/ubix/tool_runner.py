#!/usr/bin/env python3 
from openai import OpenAI
from datetime import datetime
from dataclasses import dataclass
from subprocess import CompletedProcess
import time
import threading
import os
import json
import subprocess
import libtmux
import logging
import importlib.resources

pkg_root = importlib.resources.files("ubix")

logger = logging.getLogger(__name__)


mode_path = "/tmp/ubixmode"

def contains_insensitive(text, regexlist):
    lower_text = text.lower()
    for word in regexlist:
        if(word.lower() in lower_text):
            return True
    return False

def build_mode_json():
    input_path = pkg_root / "modes.txt"  # path to the text file to read

    with open(input_path, "r", encoding="utf-8") as f:
        description = f.read().strip()

    return {
            "type": "function",
            "function": {
                "name": "change_mode",
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["sys_admin", "accountant", "scribe"],
                        }
                    },
                    "required": ["mode"],
                },
            },
        }
    

def print_json(my_json):
    print(json.dumps(my_json, indent=2))

def run_cmd(result: ExectutionResult, args: list[str]) -> CompletedProcess:
    comp = subprocess.run(args, capture_output=True, text=True)
    newResult = result
    if comp.returncode == 0:
        newResult.output = comp.stdout
    else:
        newResult.output = comp.stderr
    newResult.returncode = comp.returncode
    return newResult

@dataclass
class ExecutionResult:
    returncode: int
    tool: str
    args: dict[str, str]
    response: str
    output: str

class ToolRunner():
    def __init__(self, test_mode=False):
        self.change_mode("sys_admin")
        self.mode_context = self.get_mode_context("sys_admin")
        self.insert_locked = False
        self.test_mode = test_mode
        api_key = os.environ.get("MOONSHOT_API_KEY")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.moonshot.ai/v1",
        )

    def get_mode(self):
        return self.mode

    def change_mode(self, mode):
        self.mode = mode
        assistant_tools_path = pkg_root / "assistants" / mode / "functions.json"
        with open(assistant_tools_path) as f:
            tools = json.load(f)
        tools.append(build_mode_json())
        self.tools = tools
        self.mode_context = self.get_mode_context(mode)
        with open(mode_path, "w") as f:
            f.write(mode)
        return 0

    def get_mode_context(self, mode):
        context = ""
        assistant_context_path = pkg_root / "assistants" / mode / "context.txt"
        if os.path.exists(assistant_context_path):
            with open(assistant_context_path) as f:
                context = f.read()
        match mode:
            case "sys_admin":
                context = context
            case "accountant":
                context = context
            case "scribe":
                server = libtmux.Server()
                for session in server.sessions:
                    for window in session.windows:
                        context += str(window.panes)
        return f'Here is some useful context for executing commands in {mode} mode: {context}'

        

    def execute_tool(self, tool, arguments, command):
        args = json.loads(arguments)
        result = ExecutionResult(0, tool, args, "", "")
        if self.test_mode:
            return ExecutionResult(0, tool, args, f'fake {tool} ran successfully', "I am a fake AI response")
        ledger_path = pkg_root / "test.journal"
        match self.mode:
            case "sys_admin":
                match tool:
                    case "open_application":
                        cmd = args['application']
                        if(args['file_path']):
                            cmd += " "
                            cmd += args['file_path']
                        result = run_cmd(result, [cmd, "&"])
                    case "edit_bt_connection":
                        device_mac = args['device_mac']
                        action = args['connect_or_disconnect']
                        result = run_cmd(result, ["bluetoothctl", action, device_mac])

                    case "media_player":
                        action = args['action']
                        result = run_cmd(result, ["playerctl", action])
                        return f"{result.stdout}"
                    case "print_center":
                        file_path = args['file_path'] 
                        result = ""
                        if(args['page_start']):
                            start =args['page_start'] 
                            end = args['page_end'] 
                            result = run_cmd(result, ["lp", "-o", "fit-to-page", "-P", f'{start}-{end}', file_path])
                        else:
                            result = run_cmd(result, ["lp", "-o", "fit-to-page", file_path])
                    case "change_mode":
                        result.returncode = self.change_mode(args['mode'])
                    case _:
                        result.returncode = 2
            case "accountant":
                match tool:
                    case "create_ledger_entry":
                        date = datetime.today().strftime('%Y-%m-%d')
                        ledger_entry = (
                            f"{date} {args['entry_description']}\n"
                            f"    {args['debit_account']}    {args['debit_amount']}\n"
                            f"    {args['credit_account']}    {args['credit_amount']}\n\n"
                        )
                        with open(ledger_path, "a") as f:
                            f.write(ledger_entry)
                        result.output = f"Added entry:\n{ledger_entry}"
                    case "display_ledger_file":
                        with open(ledger_path) as f:
                            result.output = f.read()
                    case "change_mode":
                        result.returncode = self.change_mode(args['mode'])
            case "scribe":
                match tool:
                    case "set_session_window_pane":
                        result = run_cmd(result, ["muxtalk", "set", args['session_name'], args['window_number'], 0])
                    case "set_enter_mode":
                        result = run_cmd(result, ["muxtalk", "setenter", args['state']])
                    case "write":
                        result = run_cmd(result, ["muxtalk", "talk", command])
                    case "change_mode":
                        result.returncode = self.change_mode(args['mode'])
        return result



    def execute(self, command) -> ExecutionResult:
        result = ExecutionResult(0, "notool", {}, "", "")
        fake_args = json.dumps([])
        if self.get_mode() == "scribe":
            if command == "lock insert" or command == "unlock insert":
                self.insert_locked = command.split()[0] == "lock"
                result.tool = "toggle_insert"
                return result
            elif self.insert_locked:
                result = self.execute_tool("write", fake_args, command)
                return result
        tools = self.tools
        with open(pkg_root / "prompt.md") as f:
            prompt = f.read()
        messages = [
                {"role" : "user", "content": command},
                {"role" : "system", "content": prompt},
                {"role" : "system", "content": self.mode_context},
                ]

        message = self.send_messages(messages)
        messages.append(message)

        if message.tool_calls:
            #currently if the tool calls gets replenished during a tool call what happens?
            for i in range(0, len(message.tool_calls)):
                tool = message.tool_calls[i]
                tool_name = tool.function.name
                tool_id = tool.id
                tool_args = tool.function.arguments

                result = self.execute_tool(tool_name, tool_args, command)
                logger.info(f'tool name: {tool_name} result: {result.output}')
                #add tool call result to messages history
                tool_result_message = {"role" : "tool", "tool_call_id": tool_id, "content" : result.output}
                messages.append(tool_result_message)
                #send new history to model
                message = self.send_messages(messages)
                messages.append(message)
                result.response = message.content
        return result
            

    def send_messages(self, messages):
        response = self.client.chat.completions.create(
            model="kimi-k2.6",
            messages=messages,
            tools=self.tools,
        )
        return response.choices[0].message
