#!/usr/bin/env python3
"""Open the ubix chat page in a bare floating window, like the old alacritty floatterm."""
import json
import os
import shutil
import subprocess
import sys

import httpx

SERVER_URL = os.environ.get("UBIX_SERVER", "http://127.0.0.1:4096")
#same class the alacritty window used, so the i3 floating rule and the
#i3-floatterm-focus / i3-floatterm-hide bindings keep working unchanged
WINDOW_CLASS = "floatterm"
#a profile of its own: chromium only honours --class when it starts a new
#process, and it keeps the chat's settings away from your normal browser
PROFILE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "ubix", "chat-profile"
)
BROWSERS = ["chromium", "brave", "google-chrome-stable"]


def window_exists():
    result = subprocess.run(
        ["xdotool", "search", "--class", WINDOW_CLASS], capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def write_profile_prefs():
    #use the window manager's frame instead of chromium's own title bar,
    #so i3's "border pixel" leaves no title bar at all
    prefs_path = os.path.join(PROFILE_DIR, "Default", "Preferences")
    if os.path.exists(prefs_path):
        return
    os.makedirs(os.path.dirname(prefs_path), exist_ok=True)
    with open(prefs_path, "w") as f:
        json.dump({"browser": {"custom_chrome_frame": False}}, f)


def main():
    try:
        httpx.get(f"{SERVER_URL}/session", timeout=2).raise_for_status()
    except httpx.HTTPError:
        message = f"ubix-server is not running at {SERVER_URL}, start it with: ubix-server"
        #from a keybinding there is no terminal to print to
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "ubix-chat", message])
        sys.exit(message)

    if shutil.which("xdotool") and window_exists():
        #already open: bring it back (i3 focus also un-hides it from the scratchpad)
        subprocess.run(["i3-msg", f'[class="{WINDOW_CLASS}"] focus'], capture_output=True)
        return

    browser = next((b for b in BROWSERS if shutil.which(b)), None)
    if browser is None:
        sys.exit(f"ubix-chat needs one of: {', '.join(BROWSERS)}")

    write_profile_prefs()
    #?app tells the page it is in the bare window, where it blocks reloading
    subprocess.Popen(
        [
            browser,
            f"--app={SERVER_URL}/?app",
            f"--class={WINDOW_CLASS}",
            f"--user-data-dir={PROFILE_DIR}",
            "--window-size=550,500",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


if __name__ == "__main__":
    main()
