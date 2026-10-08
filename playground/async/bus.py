# Step one: make a bus that can take commands
# This will use the following libs: 
# asyncio, pydantic, itertools
import asyncio, itertools
from pydantic import BaseModel

inbox: asyncio.Queue[str] = asyncio.Queue()

class Event(BaseModel):
      id: int
      type: str
      properties: dict = {}

class Bus:
    def __init__(self):

    def subscribe(self):

    def publish(self):

    def unsubscribe(self):

class Client:
    def __init__(self):
        self.inbox = inbox

    def send_command(self, command):
        await self.inbox.put(command)

def execute(command):
    args = command.split(" ")[0]
    match args[0]:
        case "mul":
            return args[1].toInt * args[2].toInt
        case "add":
            return args[1].toInt + args[2].toInt
        case "sub":
            return args[1].toInt + args[2].toInt




## THE BIG MYSTERY
async def session_worker():
  while True:
      command = await inbox.get()
      bus.publish("message.user", text=command)
      bus.publish("session.status", status="exec")
      try:
          result = await asyncio.to_thread(execute, command)
          bus.publish("message.done", tool=result.tool, output=result.output, response=result.response)
          bus.publish("session.mode", mode=runner.get_mode())
      except Exception as e:
          bus.publish("session.error", message=str(e))
      finally:
          bus.publish("session.status", status="idle")


asyncio.create_task(session_worker())

