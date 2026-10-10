"""Single-line scrolling LED matrix. Shift one column, never redraw the banner."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from melon_lua import MelsaveSession
from melon_lua.packages.text_printer import get_pixel_font

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "marquee_led.melsave"

TEXT = "欢迎乘坐甜瓜铁路运输集团云水号动车组      G3611   甜瓜东→万城岛松山，本站：甜瓜东  下一站：雨林港        "
FONT = 12
SCREEN_W = 32
SCREEN_H = 16
GAP = 32

def columns_of(text: str) -> list[int]:
    font = get_pixel_font(FONT)
    w = 0
    for ch in text:
        w += FONT if ord(ch) > 127 else FONT // 2
    w = max(w, 4)
    img = Image.new("L", (w, FONT), 0)
    ImageDraw.Draw(img).text((0, 0), text, font=font, fill=255)
    px = img.load()
    if px is None:
        return [0] * w
    cols = []
    for x in range(w):
        mask = 0
        for y in range(FONT):
            v = px[x, y]
            if isinstance(v, (int, float)) and v > 100:
                mask |= 1 << y
        cols.append(mask)
    return cols

cols = columns_of(TEXT)
cols += [0] * GAP
while len(cols) % SCREEN_W:
    cols.append(0)
col_lua = "{" + ",".join(str(c) for c in cols) + "}"

lua = f"""local COLS = {col_lua}
local N = {len(cols)}
local FONT = {FONT}
local Y0 = {(SCREEN_H - FONT) // 2}
local ON = {{ x = 0.784, y = 0.28, z = 0.30, w = 1.0 }}
local OFF = {{ x = 0.0, y = 0.0, z = 0.0, w = 1.0 }}
local scroll = 0

local function paint()
    local x = 0
    while x < {SCREEN_W} do
        local mask = COLS[((scroll + x) % N) + 1]
        local y = 0
        while y < FONT do
            local bit = mask
            local i = 0
            while i < y do
                bit = math.floor(bit / 2)
                i = i + 1
            end
            if bit % 2 == 1 then
                canvas_0:setPixel(x, Y0 + y, ON)
            else
                canvas_0:setPixel(x, Y0 + y, OFF)
            end
            y = y + 1
        end
        x = x + 1
    end
end

function OnInit()
    local id = inputs.entity.target
    if id ~= nil and id ~= 0 then
        local e = Entity(id)
        if e and e._nil ~= true and e:isValid() == 1 then
            e:setColor(0, 0, 0, 0)
        end
    end
end

function OnTick()
    paint()
    scroll = (scroll + 1) % N
    canvas_0:flush()
end
"""

s = MelsaveSession()
cv = s.create_canvas(width=SCREEN_W, height=SCREEN_H, display_type="led_matrix", x=0, y=0)
so = s.get_container(cv.item_idx)
for md in so.get("mechanicData") or []:
    fp = md.get("floatParameters")
    if isinstance(fp, list) and len(fp) >= 3:
        fp[1] = float(SCREEN_W)
        fp[2] = float(SCREEN_H)
so["freezed"] = False
so["scale"] = {"x": 1.0, "y": 0.5, "z": 1.0}
so["color"] = {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.0}
chip = s.add_lua_chip(
    lua,
    x=2.5,
    y=0,
    title="单行滚动LED",
    canvases=[cv],
    inputs=[{"name": "target", "type": "entity"}],
    outputs=[{"name": "status", "type": "string", "value": "scrolling"}],
    instruction_cost=1000000,
    tps=30,
)
s.connect(cv.item_idx, "entity", chip, "target")
s.save(OUT)

with MelsaveSession(OUT) as live:
    led = live.get_container(0)
    md = led["mechanicData"][0]
    gates = json.loads(md["mechanicSerializedInputs"])
    summary = {}
    for g in gates:
        gd = g.get("GateData")
        if not gd:
            summary[g["Key"]] = None
            continue
        data = json.loads(gd)
        val = data.get("Value")
        summary[g["Key"]] = len(val) if isinstance(val, list) else val
    print("floatParameters", md.get("floatParameters"))
    print("gates", summary)
    wires = live.list_connections()
    print("wires", [(w["output_gate"], w["input_gate"]) for w in wires])
    r = live.debug_run(ticks=10)
    frames = r.get("frames") or []
    last = frames[-1] if frames else {}
    outs = (last.get("outputs") or {}).get("array_vec") or {}
    buf = next(iter(outs.values()), [])
    bright = 0
    for p in buf:
        if isinstance(p, dict) and p.get("x", 0) > 0.5:
            bright += 1
    print("error", r.get("error"), "buf", len(buf), "bright", bright, "cols", len(cols))
    print("saved", OUT)
