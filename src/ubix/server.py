#!/usr/bin/env python3
import asyncio
import itertools
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ubix.bus import Bus
from ubix.tool_runner import ToolRunner

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"

bus = Bus()
inbox: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
prompt_ids = itertools.count()
state = {"mode": "sys_admin", "status": "idle"}

STATUS_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ubix", "status.json"
)
# labels the bar shows, same as main.Mode
MODE_LABELS = {"sys_admin": "ADMIN", "accountant": "ACCT", "scribe": "SCRIBE"}


def write_status(mode: str, status: str, path=STATUS_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w") as f:
        json.dump({"mode": MODE_LABELS.get(mode, mode), "status": status}, f)
    os.replace(tmp_path, path)


def set_status(status: str):
    state["status"] = status
    bus.publish("session.status", status=status)


async def session_worker(runner: ToolRunner):
    while True:
        prompt_id, command = await inbox.get()
        bus.publish("message.user", id=prompt_id, text=command)
        set_status("exec")
        try:
            # execute is blocking (OpenAI client + subprocess), so it runs on a
            # thread; the loop keeps serving /event and /session/prompt meanwhile
            result = await asyncio.to_thread(runner.execute, command)
            bus.publish("message.done", **asdict(result))
            if runner.get_mode() != state["mode"]:
                state["mode"] = runner.get_mode()
                bus.publish("session.mode", mode=state["mode"])
        except Exception as e:
            logger.exception("execute failed")
            bus.publish("session.error", message=str(e))
        finally:
            set_status("idle")


async def status_writer(q: asyncio.Queue):
    # just another bus subscriber, like a web client, but its output is a file
    mode, status = state["mode"], state["status"]
    write_status(mode, status)
    while True:
        ev = await q.get()
        if ev.type == "session.status":
            status = ev.properties["status"]
        elif ev.type == "session.mode":
            mode = ev.properties["mode"]
        else:
            continue
        write_status(mode, status)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # replaces main(): runs once when uvicorn starts, before any request
    runner = ToolRunner()
    state["mode"] = runner.get_mode()
    # subscribe before the worker starts so the writer can't miss an event
    status_q = bus.subscribe()
    tasks = [
        asyncio.create_task(status_writer(status_q)),
        asyncio.create_task(session_worker(runner)),
    ]
    yield
    for t in tasks:
        t.cancel()
    bus.unsubscribe(status_q)
    write_status(state["mode"], "off")


app = FastAPI(lifespan=lifespan)


class Prompt(BaseModel):
    text: str


@app.post("/session/prompt", status_code=202)
async def prompt(p: Prompt):
    # replaces Client.send_command: queue it and return immediately.
    # message.queued lets clients show it now, even if the worker is busy
    prompt_id = next(prompt_ids)
    bus.publish("message.queued", id=prompt_id, text=p.text)
    await inbox.put((prompt_id, p.text))
    return {"id": prompt_id, "queued": inbox.qsize()}


class ClientStatus(BaseModel):
    status: Literal["rec", "trans", "idle"]


@app.post("/client/status", status_code=204)
async def client_status(c: ClientStatus):
    # the voice client reports what the server can't see: recording/transcribing
    set_status(c.status)


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/session")
async def session():
    return state


def sse(type: str, **props) -> str:
    return f"data: {json.dumps({'type': type, 'properties': props})}\n\n"


@app.get("/event")
async def events():
    # replaces read_queue: one subscriber queue per HTTP connection
    async def stream():
        q = bus.subscribe()
        try:
            yield sse("server.connected", **state)
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=10)
                    yield f"data: {ev.model_dump_json()}\n\n"
                except TimeoutError:
                    yield sse("server.heartbeat")
        finally:
            # runs when the client disconnects (generator is cancelled)
            bus.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream")


def main():
    import uvicorn
    logging.basicConfig(format="%(asctime)s %(name)s %(message)s", level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=4096)


if __name__ == "__main__":
    main()
