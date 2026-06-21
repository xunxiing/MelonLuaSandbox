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
    show_labels: bool = True,
    fit_to_content: bool = False,
    content_padding: float = 4.0,
    aspect_ratio: float | None = None,
    min_ppm: float = 2.0,
    focus_rect: tuple[float, float, float, float] | None = None,
    scale: float = 1.0,
) -> Path:
    out_path = Path(out_path)
    entities = [e for e in world.entities.values() if e.alive]
    entities.sort(key=lambda e: e.entity_id)

    # --- Compute effective view (center + ppm) ---
    eff_center_x = center_x
    eff_center_y = center_y
    eff_ppm = ppm
    grid_step = 0.5

    if focus_rect is not None:
        fx0, fy0, fx1, fy1 = focus_rect
        fx0 -= content_padding
        fx1 += content_padding
        fy0 -= content_padding
        fy1 += content_padding
        content_w = max(1e-3, fx1 - fx0)
        content_h = max(1e-3, fy1 - fy0)

        # Make the subject fill the frame vertically (good for trains)
        desired_object_h_px = 160.0
        if content_h > 0:
            eff_ppm = desired_object_h_px / content_h
        else:
            eff_ppm = float(min_ppm)
        eff_ppm = max(eff_ppm, float(min_ppm))

        eff_center_x = (fx0 + fx1) * 0.5
        eff_center_y = (fy0 + fy1) * 0.5

        pad_px = int(content_padding * eff_ppm)
        canvas_w = int(content_w * eff_ppm) + 2 * pad_px
        canvas_h = int(content_h * eff_ppm) + 2 * pad_px

        # Apply user scale (e.g. scale=5 for 5x resolution)
        if scale and scale != 1.0:
            canvas_w = int(canvas_w * scale)
            canvas_h = int(canvas_h * scale)
            eff_ppm *= scale

        # Much higher caps to allow high-res renders (user can request 5x/25x etc.)
        # Only downscale if truly enormous to avoid OOM.
        MAX_W = 30000
        MAX_H = 8000
        if canvas_w > MAX_W:
            s = MAX_W / canvas_w
            canvas_w = int(canvas_w * s)
            canvas_h = int(canvas_h * s)
            eff_ppm *= s
        if canvas_h > MAX_H:
            s = MAX_H / canvas_h
            canvas_w = int(canvas_w * s)
            canvas_h = int(canvas_h * s)
            eff_ppm *= s

        width = max(200, canvas_w)
        height = max(80, canvas_h)
        grid_step = max(0.25, round(3.0 / max(eff_ppm, 1.0), 2))
    elif fit_to_content and entities:
        minx = miny = float("inf")
        maxx = maxy = float("-inf")
        for e in entities:
            rw, rh = e.real_size()
            hw, hh = abs(rw) * 0.5, abs(rh) * 0.5
            cx_e, cy_e = e.position_x, e.position_y
            # Use the same rotation convention as drawing: positive game angle = clockwise on screen
            rad = math.radians(-e.angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                wx = cx_e + lx * cos_a - ly * sin_a
                wy = cy_e + lx * sin_a + ly * cos_a
                minx = min(minx, wx)
                maxx = max(maxx, wx)
                miny = min(miny, wy)
                maxy = max(maxy, wy)

        minx -= content_padding
        maxx += content_padding
        miny -= content_padding
        maxy += content_padding

        content_w = max(1e-3, maxx - minx)
        content_h = max(1e-3, maxy - miny)

        # Choose ppm so the core object is actually visible and fills a good part of the frame.
        # For very long thin things (trains), we want the height of the object to be decent in pixels.
        desired_object_h_px = 140.0   # make the main subject reasonably tall
        if content_h > 0:
            ppm_for_height = desired_object_h_px / content_h
        else:
            ppm_for_height = float(min_ppm)

        # Also respect the caller's requested canvas aspect if they gave a large explicit size
        if width > 800 and height > 60:
            needed_w = width * 0.92
            needed_h = height * 0.92
            ppm_w = needed_w / content_w
            ppm_h = needed_h / content_h
            eff_ppm = min(ppm_w, ppm_h)
        else:
            eff_ppm = ppm_for_height

        eff_ppm = max(eff_ppm, float(min_ppm))

        # Apply user scale before computing final canvas size
        if scale and scale != 1.0:
            eff_ppm *= scale

        eff_center_x = (minx + maxx) * 0.5
        eff_center_y = (miny + maxy) * 0.5

        # Derive output canvas size from content + eff_ppm so there is no huge empty border.
        # This makes "the core" prominent instead of a tiny line in a giant black image.
        pad_px = int(content_padding * eff_ppm)
        canvas_w = int(content_w * eff_ppm) + 2 * pad_px
        canvas_h = int(content_h * eff_ppm) + 2 * pad_px

        # Apply user scale (e.g. scale=5 for 5x resolution)
        if scale and scale != 1.0:
            canvas_w = int(canvas_w * scale)
            canvas_h = int(canvas_h * scale)
            eff_ppm *= scale

        # Soft caps to keep files reasonable while keeping the object big
        if canvas_w > 9000:
            s = 9000 / canvas_w
            canvas_w = int(canvas_w * s)
            canvas_h = int(canvas_h * s)
            eff_ppm *= s
        if canvas_h > 1600:
            s = 1600 / canvas_h
            canvas_w = int(canvas_w * s)
            canvas_h = int(canvas_h * s)
            eff_ppm *= s

        width = max(200, canvas_w)
        height = max(80, canvas_h)

        grid_step = max(0.25, round(3.0 / max(eff_ppm, 1.0), 2))

    # --- Create image and draw ---
    img = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(img)

    if show_grid:
        step = grid_step
        x0 = eff_center_x - (width * 0.6 / eff_ppm)
        x1 = eff_center_x + (width * 0.6 / eff_ppm)
        y0 = eff_center_y - (height * 0.6 / eff_ppm)
        y1 = eff_center_y + (height * 0.6 / eff_ppm)
        gx = math.floor(x0 / step) * step
        while gx <= x1:
            p1 = _world_to_px(gx, y0, eff_center_x, eff_center_y, eff_ppm, width, height)
            p2 = _world_to_px(gx, y1, eff_center_x, eff_center_y, eff_ppm, width, height)
            draw.line([p1, p2], fill=GRID, width=1)
            gx += step
        gy = math.floor(y0 / step) * step
        while gy <= y1:
            p1 = _world_to_px(x0, gy, eff_center_x, eff_center_y, eff_ppm, width, height)
            p2 = _world_to_px(x1, gy, eff_center_x, eff_center_y, eff_ppm, width, height)
            draw.line([p1, p2], fill=GRID, width=1)
            gy += step

    # origin cross
    ox, oy = _world_to_px(0, 0, eff_center_x, eff_center_y, eff_ppm, width, height)
    draw.line([(ox - 14, oy), (ox + 14, oy)], fill=ORIGIN, width=2)
    draw.line([(ox, oy - 14), (ox, oy + 14)], fill=ORIGIN, width=2)

    entities = [e for e in world.entities.values() if e.alive]
    entities.sort(key=lambda e: e.entity_id)

    for e in entities:
        rw, rh = e.real_size()
        # Use absolute sizes for drawing (negative scale means flip, not negative size)
        rw = abs(rw)
        rh = abs(rh)
        hw, hh = rw * 0.5, rh * 0.5
        cx_e, cy_e = e.position_x, e.position_y
        # Invert rotation sign: game positive angle appears clockwise on screen in this preview.
        # We treat positive game angle as clockwise, so for math we use negative rad.
        rad = math.radians(-e.angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        # flip flag for later (negative scale means mirrored)
        flip_x = e.scale_x < 0
        flip_y = e.scale_y < 0

        corners = []
        for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            wx = cx_e + lx * cos_a - ly * sin_a
            wy = cy_e + lx * sin_a + ly * cos_a
            corners.append(_world_to_px(wx, wy, eff_center_x, eff_center_y, eff_ppm, width, height))

        sprite = None
        # Prefer explicit custom melmod texture if present on the entity
        tex_path = getattr(e, "custom_texture_png", None) or e.sprite_path
        if tex_path and Path(tex_path).is_file():
            try:
                sprite = Image.open(tex_path).convert("RGBA")
            except OSError:
                sprite = None

        if sprite is not None:
            tw, th = sprite.size
            target_w = max(4, int(rw * eff_ppm))
            target_h = max(4, int(rh * eff_ppm))
            sprite = sprite.resize((target_w, target_h), Image.Resampling.NEAREST)

            # Rotate sprite if the entity has non-zero angle.
            # Game positive = clockwise on screen, PIL rotate positive = CCW, so we pass +angle to match.
            if abs(e.angle) > 0.05:
                sprite = sprite.rotate(e.angle, resample=Image.Resampling.NEAREST, expand=True)

            px, py = _world_to_px(cx_e, cy_e, eff_center_x, eff_center_y, eff_ppm, width, height)
            paste_x = int(px - sprite.width / 2)
            paste_y = int(py - sprite.height / 2)
            img.paste(sprite, (paste_x, paste_y), sprite)
        else:
            # Special colors for locomotive / mechanical subparts
            name_lower = (e.name or "").lower()
            oid = e.object_id or 0

            if "motor" in name_lower or oid == 131:
                fill = (90, 95, 105, 255)
                outline = (60, 200, 255, 255)  # blue accent like real motors
            elif "piston" in name_lower or oid == 133:
                fill = (110, 115, 125, 255)
                outline = (200, 200, 210, 255)
            elif "wheel" in name_lower or oid == 121:
                fill = (50, 50, 55, 255)
                outline = (220, 220, 230, 255)
            elif "handle" in name_lower:
                fill = (130, 100, 70, 255)
                outline = (200, 180, 150, 255)
            elif oid == 76:  # MetalRod - already handled by line, but fallback
                fill = (160, 165, 175, 255)
                outline = (120, 125, 135, 255)
            elif oid == 202:
                fill = (200, 120, 60, 220)
                outline = (255, 255, 255, 180)
            else:
                fill = (140, 160, 200, 200)
                outline = (255, 255, 255, 180)

            # For very thin rods use thick line instead of polygon
            aspect = rw / max(rh, 1e-6)
            is_rod_like = (aspect > 4.0 or aspect < 0.25) and min(rw, rh) < 0.6
            if is_rod_like:
                length = max(rw, rh)
                thick = max(3.0, min(rw, rh) * eff_ppm * 0.8)
                half = length * 0.5
                dx = math.cos(rad) * half
                dy = math.sin(rad) * half
                x1, y1 = cx_e - dx, cy_e - dy
                x2, y2 = cx_e + dx, cy_e + dy
                p1 = _world_to_px(x1, y1, eff_center_x, eff_center_y, eff_ppm, width, height)
                p2 = _world_to_px(x2, y2, eff_center_x, eff_center_y, eff_ppm, width, height)
                draw.line([p1, p2], fill=fill, width=int(thick))
                cap_r = max(2, int(thick * 0.35))
                draw.ellipse([p1[0]-cap_r, p1[1]-cap_r, p1[0]+cap_r, p1[1]+cap_r], fill=outline)
                draw.ellipse([p2[0]-cap_r, p2[1]-cap_r, p2[0]+cap_r, p2[1]+cap_r], fill=outline)
            else:
                draw.polygon(corners, fill=fill, outline=outline)

        if show_labels:
            label = f"id={e.entity_id} oid={e.object_id or '?'}"
            tx, ty = _world_to_px(cx_e, cy_e + hh + 0.08, eff_center_x, eff_center_y, eff_ppm, width, height)
            draw.text((tx - 20, ty), label, fill=(220, 220, 230, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, "PNG")

    # Optional target marker
    if show_target and target_x is not None and target_y is not None:
        tx, ty = _world_to_px(target_x, target_y, eff_center_x, eff_center_y, eff_ppm, width, height)
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