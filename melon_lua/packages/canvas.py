"""Canvas Package for MelonLuaSandbox.

Provides hardware-abstracted Canvas drawing support for LED Matrix Displays and
Text Screens. Managed from Python SDK side, with static gate wiring and Lua preamble injection.
"""
from __future__ import annotations

from typing import Optional


class CanvasInstance:
    """Represents a managed Canvas instance in Python SDK."""

    def __init__(
        self,
        canvas_id: int | str,
        item_idx: int,
        width: int = 32,
        height: int = 32,
        display_type: str = "led_matrix",
    ):
        self.canvas_id = str(canvas_id)
        self.item_idx = int(item_idx)
        self.width = int(width)
        self.height = int(height)
        self.display_type = display_type

        # Identifiers used for wiring and Lua generation
        self.lua_var = f"canvas_{self.canvas_id}"
        self.gate_key = f"canvas_out_{self.canvas_id}"

    def generate_lua_preamble(self) -> str:
        """Generate static Lua preamble code for this canvas instance."""
        total_pixels = self.width * self.height

        if self.display_type == "led_matrix":
            # For LED Matrix (objectId=596836672 / 424):
            # Transmits Vector4 color array to led-matrix-data gate with Smart Differential Incremental Writes
            return f"""-- Canvas Instance: {self.lua_var} ({self.width}x{self.height} LED Matrix)
local _buf_{self.canvas_id} = {{}}
local _dirty_{self.canvas_id} = {{}}
local _dirty_cnt_{self.canvas_id} = 0
local _total_{self.canvas_id} = {total_pixels}
local _w_{self.canvas_id} = {self.width}
local _h_{self.canvas_id} = {self.height}

for _i = 1, _total_{self.canvas_id} do
    _buf_{self.canvas_id}[_i] = {{x=0, y=0, z=0, w=1}}
end

local function _clear_px_{self.canvas_id}(r, g, b, a)
    if type(r) == "table" then
        g = r.g or r.y or r[2] or 0
        b = r.b or r.z or r[3] or 0
        a = r.a or r.w or r[4] or 1
        r = r.r or r.x or r[1] or 0
    else
        r = r or 0; g = g or 0; b = b or 0; a = a or 1
    end

    -- Smart Differential Clear: clear modified dirty pixels only when dirty_cnt < half total
    if _dirty_cnt_{self.canvas_id} > 0 and _dirty_cnt_{self.canvas_id} < (_total_{self.canvas_id} / 2) then
        for _i = 1, _dirty_cnt_{self.canvas_id} do
            local _idx = _dirty_{self.canvas_id}[_i]
            local _p = _buf_{self.canvas_id}[_idx]
            if _p.x ~= r or _p.y ~= g or _p.z ~= b or _p.w ~= a then
                _p.x = r; _p.y = g; _p.z = b; _p.w = a
            end
        end
    else
        for _i = 1, _total_{self.canvas_id} do
            local _p = _buf_{self.canvas_id}[_i]
            if _p.x ~= r or _p.y ~= g or _p.z ~= b or _p.w ~= a then
                _p.x = r; _p.y = g; _p.z = b; _p.w = a
            end
        end
    end
    _dirty_cnt_{self.canvas_id} = 0
end

local function _set_px_{self.canvas_id}(x, y, r, g, b, a)
    x = math.floor(x or 0); y = math.floor(y or 0)
    if x >= 0 and x < _w_{self.canvas_id} and y >= 0 and y < _h_{self.canvas_id} then
        local _idx = y * _w_{self.canvas_id} + x + 1
        local _p = _buf_{self.canvas_id}[_idx]
        local _nx, _ny, _nz, _nw
        if type(r) == "table" then
            _nx = r.r or r.x or r[1] or 0
            _ny = r.g or r.y or r[2] or 0
            _nz = r.b or r.z or r[3] or 0
            _nw = r.a or r.w or r[4] or 1
        else
            _nx = r or 0; _ny = g or 0; _nz = b or 0; _nw = a or 1
        end
        if _p.x ~= _nx or _p.y ~= _ny or _p.z ~= _nz or _p.w ~= _nw then
            _p.x = _nx; _p.y = _ny; _p.z = _nz; _p.w = _nw
            _dirty_cnt_{self.canvas_id} = _dirty_cnt_{self.canvas_id} + 1
            _dirty_{self.canvas_id}[_dirty_cnt_{self.canvas_id}] = _idx
        end
    end
end

local function _flush_{self.canvas_id}()
    if outputs and outputs.array_vec then
        outputs.array_vec["{self.gate_key}"] = _buf_{self.canvas_id}
    end
end

{self.lua_var} = {{
    id = "{self.canvas_id}",
    width = _w_{self.canvas_id},
    height = _h_{self.canvas_id},
    buffer = _buf_{self.canvas_id},

    clear = function(a1, a2, a3, a4, a5)
        if type(a1) == "table" then
            _clear_px_{self.canvas_id}(a2, a3, a4, a5)
        else
            _clear_px_{self.canvas_id}(a1, a2, a3, a4)
        end
    end,

    setPixel = function(a1, a2, a3, a4, a5, a6, a7)
        if type(a1) == "table" and type(a2) ~= "table" and a3 ~= nil then
            _set_px_{self.canvas_id}(a2, a3, a4, a5, a6, a7)
        else
            _set_px_{self.canvas_id}(a1, a2, a3, a4, a5, a6)
        end
    end,

    flush = _flush_{self.canvas_id}
}}
"""
        else:
            raise ValueError(f"Unsupported display_type: {self.display_type}")


class CanvasCluster:
    """Manages a grid of hardware displays for multi-chip parallel rendering."""

    def __init__(
        self,
        cols: int = 2,
        rows: int = 2,
        tile_width: int = 32,
        tile_height: int = 32,
        display_type: str = "led_matrix",
    ):
        self.cols = cols
        self.rows = rows
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.total_width = cols * tile_width
        self.total_height = rows * tile_height
        self.display_type = display_type
        self.grid: list[list[CanvasInstance]] = []

    def get_tile(self, col: int, row: int) -> CanvasInstance:
        return self.grid[row][col]


class ParallelCanvasGroup:
    """Represents a set of spawned Worker Chips and optional Master Chip driving a CanvasCluster."""

    def __init__(
        self,
        cluster: CanvasCluster,
        master_chip_idx: Optional[int] = None,
        worker_chip_indices: list[list[int]] | None = None,
    ):
        self.cluster = cluster
        self.master_chip_idx = master_chip_idx
        self.worker_chip_indices = worker_chip_indices or []


def generate_worker_tile_preamble(col: int, row: int, cluster: CanvasCluster, canvas: CanvasInstance) -> str:
    """Generate sub-viewport coordinate helper preamble for worker chips."""
    gx = col * cluster.tile_width
    gy = row * cluster.tile_height
    return f"""-- Parallel Tile Context: Col {col}, Row {row} (Viewport X:{gx}, Y:{gy})
local _tile_col_{canvas.canvas_id} = {col}
local _tile_row_{canvas.canvas_id} = {row}
local _tile_gx_{canvas.canvas_id} = {gx}
local _tile_gy_{canvas.canvas_id} = {gy}

canvas_tile_{canvas.canvas_id} = {{
    col = {col},
    row = {row},
    global_x = _tile_gx_{canvas.canvas_id},
    global_y = _tile_gy_{canvas.canvas_id},
    width = {cluster.tile_width},
    height = {cluster.tile_height},

    in_bounds = function(gx, gy)
        return gx >= _tile_gx_{canvas.canvas_id} and gx < (_tile_gx_{canvas.canvas_id} + {cluster.tile_width}) and
               gy >= _tile_gy_{canvas.canvas_id} and gy < (_tile_gy_{canvas.canvas_id} + {cluster.tile_height})
    end,

    set_global_pixel = function(a1, a2, a3, a4, a5, a6, a7)
        local gx, gy, r, g, b, a
        if type(a1) == "table" and type(a2) ~= "table" and a3 ~= nil then
            gx, gy, r, g, b, a = a2, a3, a4, a5, a6, a7
        else
            gx, gy, r, g, b, a = a1, a2, a3, a4, a5, a6
        end
        if gx >= _tile_gx_{canvas.canvas_id} and gx < (_tile_gx_{canvas.canvas_id} + {cluster.tile_width}) and
           gy >= _tile_gy_{canvas.canvas_id} and gy < (_tile_gy_{canvas.canvas_id} + {cluster.tile_height}) then
            local lx = math.floor(gx - _tile_gx_{canvas.canvas_id})
            local ly = math.floor(gy - _tile_gy_{canvas.canvas_id})
            local idx = ly * {canvas.width} + lx + 1
            local p = _buf_{canvas.canvas_id}[idx]
            if type(r) == "table" then
                p.x = r.r or r.x or r[1] or 0
                p.y = r.g or r.y or r[2] or 0
                p.z = r.b or r.z or r[3] or 0
                p.w = r.a or r.w or r[4] or 1
            else
                p.x = r or 0; p.y = g or 0; p.z = b or 0; p.w = a or 1
            end
        end
    end
}}
"""
