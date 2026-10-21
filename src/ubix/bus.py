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
