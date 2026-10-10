"""4x 32x16 LED cabin board. One chip paints a 128x16 strip and slices it."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from melon_lua import MelsaveSession
from melon_lua.packages.text_printer import get_pixel_font

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "cabin_board.melsave"

W, H = 128, 16
TW, TH = 32, 16
BLUE = (40, 170, 255)
WHITE = (255, 255, 255)


def blit_text(img, xy, text, size, fill):
    draw = ImageDraw.Draw(img)
    draw.text(xy, text, font=get_pixel_font(size), fill=fill)


def ring(draw, box, fill):
    draw.ellipse(box, outline=fill)


img = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(img)
ring(d, (1, 0, 14, 14), BLUE)
ring(d, (3, 2, 12, 12), BLUE)
blit_text(img, (5, 2), "1", 11, WHITE)
blit_text(img, (34, 0), "G520", 8, WHITE)
blit_text(img, (70, 1), "六合-北京北", 7, BLUE)
d.line((34, 8, 126, 8), fill=BLUE)
blit_text(img, (34, 9), "19排→01排", 6, WHITE)

px = img.load()
cols = []
for x in range(W):
    mask_b = 0
    mask_w = 0
    for y in range(H):
        r, g, b = px[x, y]
        if r > 200 and g > 200 and b > 200:
            mask_w |= 1 << y
        elif b > 80:
            mask_b |= 1 << y
    cols.append((mask_b, mask_w))

col_lua = "{" + ",".join(f"{{{b},{w}}}" for b, w in cols) + "}"

def tile_lua(index: int) -> str:
    start = index * TW
    tile = cols[start : start + TW]
    tile_lua_cols = "{" + ",".join(f"{{{b},{w}}}" for b, w in tile) + "}"
    return f"""local COLS = {tile_lua_cols}
local BLUE = {{ x = 0.16, y = 0.67, z = 1.0, w = 1.0 }}
local WHITE = {{ x = 1.0, y = 1.0, z = 1.0, w = 1.0 }}
local OFF = {{ x = 0.0, y = 0.0, z = 0.0, w = 1.0 }}
local tick = 0

local function bit_on(mask, y)
    local bit = mask
    local i = 0
    while i < y do
        bit = math.floor(bit / 2)
        i = i + 1
    end
    if bit % 2 == 1 then
        return 1
    end
    return 0
end

function OnTick()
    tick = tick + 1
    local x = 0
    while x < {TW} do
        local pair = COLS[x + 1]
        local y = 0
        while y < {TH} do
            if bit_on(pair[2], y) == 1 then
                canvas_0:setPixel(x, y, WHITE)
            elseif bit_on(pair[1], y) == 1 then
                canvas_0:setPixel(x, y, BLUE)
            else
                canvas_0:setPixel(x, y, OFF)
            end
            y = y + 1
        end
        x = x + 1
    end
    canvas_0:flush()
end
"""

s = MelsaveSession()
canvases = []
for i in range(4):
    cv = s.create_canvas(
        width=TW, height=TH, display_type="led_matrix", x=i * 1.6, y=0
    )
    so = s.get_container(cv.item_idx)
    for md in so.get("mechanicData") or []:
        fp = md.get("floatParameters")
        if isinstance(fp, list) and len(fp) >= 3:
            fp[1] = float(TW)
            fp[2] = float(TH)
    so["freezed"] = False
    so["scale"] = {"x": 1.0, "y": 0.5, "z": 1.0}
    so["color"] = {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.0}
    canvases.append(cv)

for i, cv in enumerate(canvases):
    s.add_lua_chip(
        tile_lua(i),
        x=i * 1.6,
        y=-1.2,
        title=f"水牌{i + 1}",
        canvases=[cv],
        outputs=[{"name": "status", "type": "string", "value": str(i + 1)}],
        instruction_cost=1000000,
        tps=30,
    )
s.save(OUT)

with MelsaveSession(OUT) as live:
    wires = live.list_connections()
    print("wires", [(w["output_gate"], w["input_gate"]) for w in wires])
    print("chips", len(live._lua_sources) if hasattr(live, "_lua_sources") else "?")
    for idx in range(4, 8):
        r = live.debug_run(ticks=1, container_idx=idx)
        frames = r.get("frames") or []
        last = frames[-1] if frames else {}
        outs = (last.get("outputs") or {}).get("array_vec") or {}
        bright = 0
        for buf in outs.values():
            for p in buf:
                if isinstance(p, dict) and (p.get("x", 0) > 0.05 or p.get("z", 0) > 0.05):
                    bright += 1
        print("chip", idx, "error", r.get("error"), "bright", bright)
    print("saved", OUT)
