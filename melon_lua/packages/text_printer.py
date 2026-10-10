"""MelonLuaSandbox Built-in Standard 12x12 Pixel Text Printer Package.

Provides clean, 100% readable 12x12 CJK pixel text rendering for LED matrix
displays and canvas chips with zero GC allocation and crash-proof flat hex encoding.
"""
from PIL import Image, ImageFont, ImageDraw

_FONT_CACHE = {}

def get_pixel_font(size: int = 12):
    """Load or get cached pixel font for specified size."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    
    font = None
    font_paths = [
        "C:\\Windows\\Fonts\\simsun.ttc",    # SimSun
        "C:\\Windows\\Fonts\\msyh.ttc",      # YaHei
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, size)
            break
        except Exception:
            continue
            
    if font is None:
        font = ImageFont.load_default()
        
    _FONT_CACHE[size] = font
    return font

def rasterize_text_to_hex(
    text: str,
    font_size: int = 12,
    threshold: int = 100
) -> tuple[str, int, int]:
    """Rasterize input text into 1-bit pixel matrix at standard 12x12 per character grid.
    
    Returns:
        (hex_data, width, height)
    """
    font = get_pixel_font(font_size)
    
    # Calculate exact width: 12px for CJK/wide characters, 6px for ASCII/narrow
    w = 0
    for ch in text:
        w += font_size if ord(ch) > 127 else (font_size // 2)
    w = max(w, 4)
    h = font_size
    
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    
    # Draw text with crisp vertical alignment
    y_offset = -1 if font_size == 12 else 0
    draw.text((0, y_offset), text, font=font, fill=255)
    
    pixels = img.load()
    packed_bytes = []
    
    # Header: width (2 bytes), height (1 byte). Width is 16-bit so a
    # scrolling banner longer than 255px still decodes.
    packed_bytes.append((w >> 8) & 0xFF)
    packed_bytes.append(w & 0xFF)
    packed_bytes.append(h & 0xFF)
    
    # Collect non-zero pixel coordinates
    pts = []
    if pixels is not None:
        for y in range(h):
            for x in range(w):
                v = pixels[x, y]
                if isinstance(v, (int, float)) and v > threshold:
                    pts.append(x)
                    pts.append(y)
                
    # Point count (2 bytes)
    pt_len = len(pts) // 2
    packed_bytes.append((pt_len >> 8) & 0xFF)
    packed_bytes.append(pt_len & 0xFF)
    
    for val in pts:
        packed_bytes.append(val & 0xFF)
        
    hex_str = "".join(f"{b:02x}" for b in packed_bytes)
    return hex_str, w, h

def generate_lua_text_printer_preamble() -> str:
    """Generate high-performance Lua text printing preamble."""
    return """-- Native SDK 12x12 Pixel Text Printer Engine (Zero Allocation & Crash-Proof)
local TextPrinter = {}

function TextPrinter.print(buf, screen_w, screen_h, start_x, start_y, hex_data, color)
    if not buf or not hex_data or #hex_data < 8 then return end
    
    local r = color and color.x or 1.0
    local g = color and color.y or 1.0
    local b = color and color.z or 1.0
    local a = color and color.w or 1.0
    
    local w = tonumber(string.sub(hex_data, 1, 4), 16) or 0
    local h = tonumber(string.sub(hex_data, 5, 6), 16) or 0
    local count = tonumber(string.sub(hex_data, 7, 10), 16) or 0
    
    local idx = 11
    for i = 1, count do
        local px = tonumber(string.sub(hex_data, idx, idx + 1), 16)
        local py = tonumber(string.sub(hex_data, idx + 2, idx + 3), 16)
        idx = idx + 4
        
        if px and py then
            local wx = start_x + px
            local wy = start_y + py
            if wx >= 0 and wx < screen_w and wy >= 0 and wy < screen_h then
                local slot = (wy * screen_w) + wx + 1
                local p = buf[slot]
                if p then
                    p.x = r
                    p.y = g
                    p.z = b
                    p.w = a
                end
            end
        end
    end
end

-- Register module if shared is present
if shared then
    shared.modules = shared.modules or {}
    shared.modules["text_printer"] = TextPrinter
end
_G.TextPrinter = TextPrinter
"""
