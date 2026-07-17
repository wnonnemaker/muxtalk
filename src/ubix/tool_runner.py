#!/usr/bin/env python3 
from openai import OpenAI
from datetime import datetime
import time
import threading
import os
import json
import subprocess


mode_path = "/tmp/ubixmode"

def contains_insensitive(text, regexlist):
    lower_text = text.lower()
    for word in regexlist:
        if(word.lower() in lower_text):
            return True
    return False

def build_mode_json():
    input_path = "modes.txt"  # path to the text file to read

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

class ToolRunner():
    def __init__(self):
        self.change_mode("sys_admin")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.anthropic.com/v1/",
        )

    def get_mode(self):
        return self.mode

    def change_mode(self, mode):
        self.mode = mode
        assistant_tools_path = "assistants/" + mode + "/functions.json"
        with open(assistant_tools_path) as f:
            tools = json.load(f)
        tools.append(build_mode_json())
        self.tools = tools
        with open(mode_path, "w") as f:
            f.write(mode)
        return 0

    def execute_tool(self, tool, arguments, command):
        print(f'tool picked: {tool}')
        args = json.loads(arguments)
        ledger_path = "/home/will/projects/software/ubix/files/pyubix/test.journal"
        returncode = 0
        ok_message = "command executed successfully"
        match self.mode:
            case "sys_admin":
                match tool:
                    case "open_application":
                        application = args['application']
                        result = os.system(f"{application} &")
                        return f"{application} opened with result {result}"
                    case "change_mode":
                        returncode = self.change_mode(args['mode'])
                    case _:
                        returncode = 2
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
                        return f"Added entry:\n{ledger_entry}"
                    case "display_ledger_file":
                        with open(ledger_path) as f:
                            return f.read()
                    case "change_mode":
                        returncode = self.change_mode(args['mode'])
                    case _:
                        returncode = 2
            case "scribe":
                match tool:
                    case "set_session_window_pane":
                        returncode = subprocess.run(["muxtalk", "set", args['session_name'], args['window_number'], args['pane_number']], capture_output=True).returncode
                    case "fallback":
                        returncode = subprocess.run(["muxtalk", "talk", command]).returncode
                    case "change_mode":
                        returncode = self.change_mode(args['mode'])

        if(returncode == 0):
            return ok_message
        if(returncode == 1):
            return default_fail_message
        if(returncode == 2):
            return "Error: selected tool did not match any cases"


    def execute(self, command):
        tools = self.tools
        with open("prompt.md") as f:
            prompt = f.read()
        messages = [
                {"role" : "user", "content": command},
                {"role" : "system", "content": prompt}
                ]
        message = self.send_messages(messages)
        messages.append(message)

        print(f'PreLoop System> {message.content}')
        for i in range(0, len(message.tool_calls)):
            tool = message.tool_calls[i]
            tool_name = tool.function.name
            tool_id = tool.id
            tool_args = tool.function.arguments

            result = self.execute_tool(tool_name, tool_args, command)
            #add tool call result to messages history
            tool_result_message = {"role" : "tool", "tool_call_id": tool_id, "content" : result}
            messages.append(tool_result_message)
            #send new history to model
            message = self.send_messages(messages)
            messages.append(message)
        print(f'PostLoop System> {message.content}')
        #return mode after every call to keep callers updated on mode state
        return self.mode
            

    def send_messages(self, messages):
        response = self.client.chat.completions.create(
            model="claude-haiku-4-5",
            messages=messages,
            tools=self.tools,
            tool_choice="required"
        )
        return response.choices[0].message

runner = ToolRunner()
with open(mode_path) as f:
    data = f.read()
print(f'mode from file is: {data}')
command = "Switch to scribe mode" 
print(f'executing command: {command}')
runner.execute(command)
with open(mode_path) as f:
    data = f.read()
print(f'mode from file is: {data}')
command = "set active pane to ubix 2 0" 
print(f'executing command: {command}')
runner.execute(command)
command = "I remember it being a sunny day in philly" 
print(f'executing command: {command}')
runner.execute(command)
