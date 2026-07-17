#!/usr/bin/env python3 
import threading
from openai import OpenAI
import os
import json
import subprocess

api_key = os.environ.get("ANTHROPIC_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.anthropic.com/v1/",
)

def send_messages(messages, tools):
    response = client.chat.completions.create(
        model="claude-haiku-4-5",
        messages=messages,
        tools=tools
    )
    return response.choices[0].message

def build_mode_json():
    with open("modes.txt", "r", encoding="utf-8") as f:
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
        },
        {
            "type": "function",
            "function": {
                "name": "user_command",
                "description": "Any regular command the user is trying to issue
                to ubix",
            },
        }
    ]

class ModeManager():
    def __init__(self):
        self.mode = "sys_admin"
        self.mode_json = build_mode_json()

        with open("functions.json") as f:
            self.tools = json.load(f)

    def check_mode_switch(self):
        message = send_messages(messages, tools)
        if message.tool_calls:
            mode_switch_needed = True
            tool = response.choices[0].message.tool_calls[0]


#userinput = input("User: ")
userinput = "print the word orange, tangerine, and apple"

with open("prompt.md") as f:
    prompt = f.read()

messages = [
        {"role" : "user", "content": userinput},
        {"role" : "system", "content": prompt}
        ]

mode_tools = build_mode_json()

with open("pho_functions.json") as f:
    tools = json.load(f)

message = send_messages(messages, tools)
messages.append(message)

print(f'input: {userinput}')
print(f'tool calls: {message.tool_calls}')
print(f'system response: {message.content}')

while(message.tool_calls):
    tool = message.tool_calls.pop(0)
    name = tool.function.name
    args = json.loads(tool.function.arguments)
    print(f'args: {args}')
    match name:
        case "print_word":
            word = args['word']
            print(word)
    

#mode_switcher = threading.Thread(target=check_mode_switch, daemon=False)
#mode_switcher.start()
#mode_switcher.join()


