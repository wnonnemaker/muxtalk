#!/usr/bin/env python3
from enum import StrEnum, Enum

class Mode(StrEnum):
    sys_admin = "ADMIN"
    assistant = "ASST"
    scribe = "SCRIBE"

class Status(Enum):
    idle = "idle"
    recording = "rec"
    transcribing = "trans"
    executing = "exec"

mode = "sys_admin"
print(f'brackets: {Mode[mode]}')
print(f'brackets: {Status.recording.value}')

