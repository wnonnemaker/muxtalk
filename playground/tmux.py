#!/usr/bin/env python3
import libtmux

server = libtmux.Server()
text = "wer"
print(len(text))
for session in server.sessions:
    for window in session.windows:
        text = str(window.panes)
print(len(text))


