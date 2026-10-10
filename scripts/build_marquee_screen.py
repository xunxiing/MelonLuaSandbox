"""Text screen marquee: TMP rich text, no wrap, sub-character slide."""
import json
from pathlib import Path

from melon_lua import MelsaveSession

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "samples" / "marquee_screen.lua").read_text(encoding="utf-8")
OUT = ROOT / "marquee_screen.melsave"

s = MelsaveSession()
screen = s.add_item(261, x=0, y=0, freezed=True)
so = s.get_container(screen)
so["color"] = {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}
chip = s.add_lua_chip(
    SRC,
    x=1.4,
    y=0,
    title="单行滚动屏",
    inputs=[
        {"name": "text", "type": "string", "value": ""},
        {"name": "screen", "type": "entity"},
    ],
    outputs=[
        {"name": "text", "type": "string"},
        {"name": "color", "type": "vector"},
    ],
    tps=30,
)
s.connect(chip, "text", screen, "text")
s.connect(chip, "color", screen, "color")
s.connect(screen, "entity", chip, "screen")
s.save(OUT)

with MelsaveSession(OUT) as live:
    gates = json.loads(live.get_container(0)["mechanicData"][0]["mechanicSerializedInputs"])
    text_gate = next(g for g in gates if g["Key"] == "string")
    print("multiline", "IsMultiline\\\":false" in text_gate["GateData"] or '"IsMultiline":false' in text_gate["GateData"].replace(" ", ""))
    print("wires", [(w["output_gate"], w["input_gate"]) for w in live.list_connections()])
    r = live.debug_run(ticks=24)
    print("error", r.get("error"))
    prev = None
    for i, fr in enumerate(r.get("frames") or []):
        txt = ((fr.get("outputs") or {}).get("string") or {}).get("text", "")
        if i < 6 or txt != prev:
            print(f"t{i + 1:02d}", txt)
        prev = txt
        if "\n" in txt:
            raise SystemExit("newline leaked")
    print("saved", OUT)
