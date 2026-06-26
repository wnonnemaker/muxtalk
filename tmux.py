#!/usr/bin/env python3
import libtmux

server = libtmux.Server()
print(server.sessions)
print(server.sessions[3].windows[1])
claude = server.sessions[3].windows[1].panes[0]
fulltext = 'hello claude'
claude.send_keys(fulltext, enter=True)

