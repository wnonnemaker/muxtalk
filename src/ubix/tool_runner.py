#!/usr/bin/env python3 
from openai import OpenAI, AsyncOpenAI
from datetime import datetime
from dataclasses import dataclass
from subprocess import CompletedProcess
import asyncio
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
MAX_TOOL_ROUNDS = 5

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
    

def parse_args(arguments):
    try:
        return json.loads(arguments) or {}
    except json.JSONDecodeError:
        return {}

def print_json(my_json):
    print(json.dumps(my_json, indent=2))

@dataclass
class ExecutionResult:
    returncode: int
    tool: str
    args: dict[str, str]
    response: str
    output: str

def run_cmd(result: ExecutionResult, args: list[str]) -> ExecutionResult:
    try:
        comp = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        result.returncode = 127
        result.output = f"command not found: {args[0]}"
        return result
    if comp.returncode == 0:
        result.output = comp.stdout
    else:
        result.output = comp.stderr
    result.returncode = comp.returncode
    return result

def launch(result: ExecutionResult, args: list[str]) -> ExecutionResult:
    #gui apps keep running, so start them detached instead of waiting like run_cmd
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError:
        result.returncode = 127
        result.output = f"command not found: {args[0]}"
        return result
    result.output = f"launched {' '.join(args)}"
    return result

class ToolRunner():
    def __init__(self, test_mode=False):
        self.change_mode("sys_admin")
        self.mode_context = self.get_mode_context("sys_admin")
        self.insert_locked = False
        self.test_mode = test_mode
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        #used by execute_async, which streams the reply as it is generated
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
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
                        cmd = [args['application']]
                        if args.get('file_path'):
                            cmd.append(os.path.expanduser(args['file_path']))
                        result = launch(result, cmd)
                    case "edit_bt_connection":
                        device_mac = args['device_mac']
                        action = args['connect_or_disconnect']
                        result = run_cmd(result, ["bluetoothctl", action, device_mac])

                    case "media_player":
                        action = args['action']
                        result = run_cmd(result, ["playerctl", action])
                    case "print_center":
                        file_path = os.path.expanduser(args['file_path'])
                        if args.get('page_start'):
                            start = args['page_start']
                            end = args.get('page_end', start)
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
                    case _:
                        result.returncode = 2
            case "scribe":
                match tool:
                    case "set_session_window_pane":
                        result = run_cmd(result, ["muxtalk", "set", args['session_name'], args['window_number'], '0'])
                    case "set_enter_mode":
                        result = run_cmd(result, ["muxtalk", "setenter", args['state']])
                    case "write":
                        result = run_cmd(result, ["muxtalk", "talk", command])
                    case "change_mode":
                        result.returncode = self.change_mode(args['mode'])
                    case _:
                        result.returncode = 2
        if result.returncode == 2 and not result.output:
            result.output = f"unknown tool {tool} in {self.mode} mode"
        return result



    def scribe_shortcut(self, command) -> ExecutionResult | None:
        #scribe commands that skip the model entirely; None means ask the model
        result = ExecutionResult(0, "notool", {}, "", "")
        fake_args = json.dumps([])
        if self.get_mode() == "scribe":
            logger.info(f'Insert locked: {self.insert_locked}')
            stripped_command = command.replace(".", "")
            stripped_command = stripped_command.lower()
            if stripped_command == "lock insert" or stripped_command == "unlock insert":
                split_string = stripped_command.split()
                should_lock = stripped_command.split()[0] == "lock"
                logger.info(f'Inside stripped command if, should_lock: {should_lock}')
                self.insert_locked = should_lock
                result.tool = "toggle_insert"
                return result
            elif self.insert_locked:
                result = self.execute_tool("write", fake_args, command)
                return result
        return None

    def build_messages(self, command):
        with open(pkg_root / "prompt.md") as f:
            prompt = f.read()
        return [
                {"role" : "system", "content": prompt},
                {"role" : "system", "content": self.mode_context},
                {"role" : "user", "content": command},
                ]

    def execute(self, command) -> ExecutionResult:
        shortcut = self.scribe_shortcut(command)
        if shortcut is not None:
            return shortcut
        result = ExecutionResult(0, "notool", {}, "", "")
        messages = self.build_messages(command)

        message = self.send_messages(messages)
        messages.append(message)

        #keep going while the model asks for tools, e.g. "connect my headphones
        #then resume my music" is two rounds; capped so it can't loop forever
        for _ in range(MAX_TOOL_ROUNDS):
            if not message.tool_calls:
                break
            #every tool call in a turn needs its result before the next request
            for tool in message.tool_calls:
                result = self.execute_tool(tool.function.name, tool.function.arguments, command)
                logger.info(f'tool name: {tool.function.name} result: {result.output}')
                messages.append({"role" : "tool", "tool_call_id": tool.id, "content" : result.output or ""})
            #mode may have changed, so send with the new mode's tools
            message = self.send_messages(messages)
            messages.append(message)
        result.response = message.content or ""
        return result
            

    async def execute_async(self, command, emit) -> ExecutionResult:
        """Same loop as execute, but streams: emit(type, **props) is called with
        message.delta for each chunk of reply text, and tool.started / tool.done
        around every tool call. Tools still run on a thread, they are blocking."""
        shortcut = await asyncio.to_thread(self.scribe_shortcut, command)
        if shortcut is not None:
            return shortcut
        result = ExecutionResult(0, "notool", {}, "", "")
        messages = self.build_messages(command)

        message = await self.stream_message(messages, emit)
        messages.append(message)

        for _ in range(MAX_TOOL_ROUNDS):
            if not message.get("tool_calls"):
                break
            for call in message["tool_calls"]:
                name = call["function"]["name"]
                arguments = call["function"]["arguments"]
                emit("tool.started", call_id=call["id"], tool=name, args=parse_args(arguments))
                try:
                    result = await asyncio.to_thread(self.execute_tool, name, arguments, command)
                except json.JSONDecodeError:
                    result = ExecutionResult(2, name, {}, "", f"invalid arguments: {arguments}")
                logger.info(f'tool name: {name} result: {result.output}')
                emit("tool.done", call_id=call["id"], tool=name, args=result.args,
                     returncode=result.returncode, output=result.output)
                messages.append({"role" : "tool", "tool_call_id": call["id"], "content" : result.output or ""})
            message = await self.stream_message(messages, emit)
            messages.append(message)
        result.response = message["content"] or ""
        return result

    async def stream_message(self, messages, emit):
        stream = await self.async_client.chat.completions.create(
            model="deepseek-flash",
            messages=messages,
            tools=self.tools,
            stream=True,
        )
        content = ""
        #tool calls arrive in pieces: the id and name first, then the
        #arguments json a few characters at a time, keyed by index
        calls = {}
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content += delta.content
                emit("message.delta", text=delta.content)
            for piece in delta.tool_calls or []:
                call = calls.setdefault(piece.index, {"id": "", "name": "", "arguments": ""})
                if piece.id:
                    call["id"] = piece.id
                if piece.function and piece.function.name:
                    call["name"] += piece.function.name
                if piece.function and piece.function.arguments:
                    call["arguments"] += piece.function.arguments
        message = {"role": "assistant", "content": content or None}
        if calls:
            message["tool_calls"] = [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                for _, c in sorted(calls.items())
            ]
        return message

    def send_messages(self, messages):
        response = self.client.chat.completions.create(
            model="deepseek-flash",
            messages=messages,
            tools=self.tools,
        )
        return response.choices[0].message
