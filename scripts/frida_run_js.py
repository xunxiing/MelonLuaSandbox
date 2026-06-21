"""Run a Frida JS file against Melon Sandbox."""
import json
import sys
import time
from pathlib import Path

import frida

PACKAGE = "com.studio27.MelonPlayground"


def main():
    js_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("frida_scan_il2cpp_strings.js")
    code = js_path.read_text(encoding="utf-8")

    def on_message(message, _data):
        if message["type"] == "send":
            print(json.dumps(message.get("payload"), ensure_ascii=False, indent=2))
        elif message["type"] == "error":
            print("ERROR:", message.get("stack", message), file=sys.stderr)

    device = frida.get_usb_device(timeout=10)
    session = device.attach(PACKAGE)
    script = session.create_script(code)
    script.on("message", on_message)
    script.load()
    time.sleep(4)
    session.detach()


if __name__ == "__main__":
    main()