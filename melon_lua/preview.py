"""2D world preview with Pillow — pixel-style sprites + physics AABB."""
from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from PIL import Image, ImageDraw
except ImportError as exc:
    raise ImportError("preview requires Pillow: pip install pillow") from exc

if TYPE_CHECKING:
    from .world import WorldContext

DEFAULT_PPM = 96
BG = (30, 32, 40, 255)
GRID = (50, 54, 66, 255)
ORIGIN = (120, 180, 255, 200)


def _world_to_px(x: float, y: float, cx: float, cy: float, ppm: float, w: int, h: int) -> tuple[float, float]:
    px = w / 2 + (x - cx) * ppm
    py = h / 2 - (y - cy) * ppm
    return px, py


def render_world(
    world: "WorldContext",
    out_path: str | Path,
    *,
    width: int = 640,
    height: int = 480,
    ppm: float = DEFAULT_PPM,
    center_x: float = 0.0,
    center_y: float = 0.5,
    show_grid: bool = True,
    padding_m: float = 1.5,
    target_x: float | None = None,
    target_y: float | None = None,
    show_target: bool = True,
) -> Path:
    out_path = Path(out_path)
    img = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(img)

    if show_grid:
        step = 0.5
        x0 = center_x - padding_m
        x1 = center_x + padding_m
        y0 = center_y - padding_m
        y1 = center_y + padding_m
        gx = math.floor(x0 / step) * step
        while gx <= x1:
            p1 = _world_to_px(gx, y0, center_x, center_y, ppm, width, height)
            p2 = _world_to_px(gx, y1, center_x, center_y, ppm, width, height)
            draw.line([p1, p2], fill=GRID, width=1)
            gx += step
        gy = math.floor(y0 / step) * step
        while gy <= y1:
            p1 = _world_to_px(x0, gy, center_x, center_y, ppm, width, height)
            p2 = _world_to_px(x1, gy, center_x, center_y, ppm, width, height)
            draw.line([p1, p2], fill=GRID, width=1)
            gy += step

    ox, oy = _world_to_px(0, 0, center_x, center_y, ppm, width, height)
    draw.line([(ox - 12, oy), (ox + 12, oy)], fill=ORIGIN, width=2)
    draw.line([(ox, oy - 12), (ox, oy + 12)], fill=ORIGIN, width=2)

    entities = [e for e in world.entities.values() if e.alive]
    entities.sort(key=lambda e: e.entity_id)

    for e in entities:
        rw, rh = e.real_size()
        hw, hh = rw * 0.5, rh * 0.5
        cx_e, cy_e = e.position_x, e.position_y
        rad = math.radians(e.angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        corners = []
        for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            wx = cx_e + lx * cos_a - ly * sin_a
            wy = cy_e + lx * sin_a + ly * cos_a
            corners.append(_world_to_px(wx, wy, center_x, center_y, ppm, width, height))

        sprite = None
        if e.sprite_path and Path(e.sprite_path).is_file():
            try:
                sprite = Image.open(e.sprite_path).convert("RGBA")
            except OSError:
                sprite = None

        if sprite is not None:
            tw, th = sprite.size
            target_w = max(4, int(rw * ppm))
            target_h = max(4, int(rh * ppm))
            sprite = sprite.resize((target_w, target_h), Image.Resampling.NEAREST)
            px, py = _world_to_px(cx_e, cy_e, center_x, center_y, ppm, width, height)
            paste_x = int(px - target_w / 2)
            paste_y = int(py - target_h / 2)
            img.paste(sprite, (paste_x, paste_y), sprite)
        else:
            fill = (200, 120, 60, 220) if e.object_id == 202 else (140, 160, 200, 200)
            draw.polygon(corners, fill=fill, outline=(255, 255, 255, 180))

        label = f"id={e.entity_id} oid={e.object_id or '?'}"
        tx, ty = _world_to_px(cx_e, cy_e + hh + 0.08, center_x, center_y, ppm, width, height)
        draw.text((tx - 20, ty), label, fill=(220, 220, 230, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, "PNG")

    # Optional target marker (red cross + dot + label) for move-to demos
    if show_target and target_x is not None and target_y is not None:
        tx, ty = _world_to_px(target_x, target_y, center_x, center_y, ppm, width, height)
        tcol = (255, 70, 70, 255)
        ts = 10
        draw.line([(tx - ts, ty), (tx + ts, ty)], fill=tcol, width=2)
        draw.line([(tx, ty - ts), (tx, ty + ts)], fill=tcol, width=2)
        draw.ellipse([tx - 4, ty - 4, tx + 4, ty + 4], fill=tcol)
        try:
            draw.text((tx + 12, ty - 8), "TARGET", fill=(255, 120, 120, 255))
        except Exception:
            pass

    return out_path