#!/usr/bin/env python3
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

messages = [{"role": "user", "content": "Open brave browser"}]
message = send_messages(messages)
print(f"message: \t{message}")
print(f"User>\t {messages[0]['content']}")

tool = message.tool_calls[0]
args = json.loads(tool.function.arguments)
application = args["application"]  # e.g. "brave"
os.system(f"{application} &")
print(f"Tool: \t{tool}")
messages.append(message)

messages.append({"role": "tool", "tool_call_id": tool.id, "content": "Opened brave browser"})
message = send_messages(messages)
print(f"Model>\t {message.content}")
