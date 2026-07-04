#!/usr/bin/env python3
from openai import OpenAI
import os
import json
import subprocess
from datetime import datetime
api_key = os.environ.get("DEEPSEEK_API_KEY")
ledger_path = os.environ.get("LEDGER_FILE")


def send_messages(messages):
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=messages,
        tools=tools
    )
    return response.choices[0].message

def response_json(response):
    print(json.dumps(response.model_dump(), indent=2))

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


client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

with open("functions.json") as f:
    tools = json.load(f)

messages = []
while(True):
    usertext = input('User>')
    messages = [
            {"role" : "user", "content": "add a ten dollar expense for a mcdonlads burger"},
            {"role" : "assistant", "content": "describe what the system is doing for the user"}
            ]
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages = messages,
        tools = tools
    )
    print("Done with first call!")
    response_json(response)
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

