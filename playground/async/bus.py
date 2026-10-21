#both of these sub to bus
import asyncio, itertools
from pydantic import BaseModel

class Event(BaseModel):
      id: int
      type: str
      properties: dict = {}

class Bus:
    def __init__(self):
        self._subs : set[asyncio.Queue] = set()
        self._ids = itertools.count()

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue[Event]()
        self._subs.add(q)
        return q

    def publish(self, type: str, **props):
        ev = Event(id=next(self._ids), type=type, properties = props)
        for q in self._subs:
            q.put_nowait(ev)

    def unsubscribe(self, q):
        self._subs.discard(q)

myBus = Bus()

class Client:
    def __init__(self, id):
        self.inbox = inbox
        self.q = myBus.subscribe() 
        self.id = id

    def get_id(self):
        return self.id

    async def send_command(self, command):
        await self.inbox.put(command)

    async def get_event(self):
        task = self.q.get()
        #print(f'task is: {task}')
        return await task

async def read_queue(client: Client):
    while True:
        event = await client.get_event()
        print(f'I am client {client.get_id()} and i received event: {event}')

def execute(command):
    op, a, b = command.split()
    a, b = int(a), int(b)
    match op:
        case "mul":
            return a * b
        case "add":
            return a + b
        case "sub":
            return a - b
        case _:
            raise ValueError(f"unknown command: {op}")

async def session_worker():
  while True:
      command = await inbox.get()
      myBus.publish("message.user", text=command)
      myBus.publish("session.status", status="exec")
      try:
          result = execute(command)
          myBus.publish("message.done", result=result)
      except Exception as e:
          myBus.publish("session.error", message=str(e))
      finally:
          myBus.publish("session.status", status="idle")

inbox: asyncio.Queue[str] = asyncio.Queue()

async def main():

    client1 = Client(1)
    client2 = Client(2)

    asyncio.create_task(read_queue(client1))
    asyncio.create_task(read_queue(client2))

    session_task = asyncio.create_task(session_worker())

    print("client 1 sending 'mul 3 3'")
    await client1.send_command("mul 3 3")

    print("client 2 sending 'add 3 3'")
    await client2.send_command("add 3 3")

    await session_task

asyncio.run(main())
