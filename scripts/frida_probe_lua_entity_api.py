"""Attach to Melon Sandbox and probe entity.all / env.entityCount via IL2CPP memory.

Usage (game running, frida-server on device, adb forward tcp:27042):
  python scripts/frida_probe_lua_entity_api.py
"""
from __future__ import annotations

import json
import sys

import frida

PACKAGE = "com.studio27.MelonPlayground"
SCRIPT = r"""
(function () {
  function log(msg) { send({ type: "log", msg: String(msg) }); }

  var mods = Process.enumerateModules();
  var interesting = mods.filter(function (m) {
    var n = m.name.toLowerCase();
    return n.indexOf("il2cpp") >= 0 || n.indexOf("unity") >= 0 || n.indexOf("main") >= 0
      || n.indexOf("melon") >= 0 || n.indexOf("game") >= 0 || n.indexOf("lib") === 0;
  });
  log("modules total=" + mods.length + " interesting=" + interesting.length);
  interesting.slice(0, 40).forEach(function (m) {
    log("mod " + m.name + " base=" + m.base + " size=" + m.size);
  });

  var needles = ["EntityApiModule", "EnvironmentApiModule", "entityCount", "RegisterEnvStackGlobals"];
  var hits = [];
  var ranges = Process.enumerateRanges({ protection: "r--", coalesce: true });
  log("readable ranges=" + ranges.length);

  function scanRange(r, needle) {
    try {
      var pattern = needle.split("").map(function (c) {
        var h = c.charCodeAt(0).toString(16);
        return h.length === 1 ? "0" + h : h;
      }).join(" ");
      var ms = Memory.scanSync(r.base, r.size, pattern);
      return ms.length;
    } catch (e) {
      return 0;
    }
  }

  needles.forEach(function (needle) {
    var total = 0;
    var sample = null;
    for (var i = 0; i < ranges.length && total === 0; i++) {
      if (ranges[i].size < 0x1000 || ranges[i].size > 80 * 1024 * 1024) continue;
      var c = scanRange(ranges[i], needle);
      if (c > 0) {
        total += c;
        sample = ranges[i];
      }
    }
    if (total > 0) {
      hits.push({ needle: needle, count: total, range: sample ? String(sample.base) : null });
    }
  });
  send({ type: "string_hits", hits: hits });

  // Try Il2CppApi if class exists in global metadata path (often fails on translated builds)
  try {
    if (typeof Il2Cpp !== "undefined") {
      log("Il2Cpp frida bridge available");
    }
  } catch (e) {}

  send({ type: "done" });
})();
"""


def on_message(message, data):
    if message["type"] == "send":
        payload = message.get("payload")
        if isinstance(payload, dict):
            if payload.get("type") == "log":
                print(payload.get("msg", ""))
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload)
    elif message["type"] == "error":
        print("FRIDA ERROR:", message.get("stack", message), file=sys.stderr)


def main():
    device = frida.get_usb_device(timeout=10)
    try:
        session = device.attach(PACKAGE)
    except frida.ProcessNotFoundError:
        print(f"Process not found: {PACKAGE}. Launch the game first.", file=sys.stderr)
        sys.exit(1)

    script = session.create_script(SCRIPT)
    script.on("message", on_message)
    script.load()
    import time

    time.sleep(3)
    session.detach()
    print("probe finished")


if __name__ == "__main__":
    main()