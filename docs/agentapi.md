# Melon Lua Sandbox — Agent API Reference

This document is a compact, highly accurate API reference optimized for the AI Agent. It details the recommended high-level APIs for sandbox creation, UI building, simulation testing, and query utilities.

---

## 1. High-Level Save & Simulation API (`MelsaveSession`)

[`MelsaveSession`](file:///d:/程序/melonapk/MelonLuaSandbox/melon_lua/session.py) is the primary entry point for managing `.melsave` files and executing sandboxed simulations. It handles document building (adding items, UI controllers, wire connections) and runs physics/script execution in sandboxed environments.

### Context Management & Lifecycle
Entering a `with` block (or calling `s.load()`) transitions the session from **Document Mode** to **Runtime Mode** by spawning objects into a Box2D world and initializing the Lua VM.

> [!IMPORTANT]
> **Document Mode vs. Runtime Mode Syncing:**
> Document-level modifications (`add_item`, `add_lua_chip`, `add_ui_controller`) append directly to the raw save document data. 
> - If called **before** entering the `with` block (or before `s.load()`), these added items will be spawned into the physics world.
> - If called **inside** the `with` block (when the simulation is already active), they will *not* be spawned into the live physics world. To add live elements mid-simulation, use `s.spawn()` instead.

```python
from melon_lua import MelsaveSession

# Create session in Document Mode
s = MelsaveSession("input.melsave")

# 1. Document operations (work immediately, done before load to be simulated)
idx = s.add_item(202, x=0, y=0)

# 2. Simulation / Verification (loads doc + starts runtime when entering)
with s:
    result = s.run_chip(lua_src, ticks=100)
    assert result.get("error") is None
    
    # 3. Export (diffs live world state and outputs output.melsave)
    s.save("output.melsave")
```

### Document Building Methods (No `load()` required)
* **`s.add_item(object_id, x=0.0, y=0.0, *, z=-0.0005, rotation=0.0, scale_x=1.0, scale_y=1.0, color=None, dynamic=True, freezed=False, template=None) -> int`**  
  Spawns a catalog item by its numeric `object_id` (e.g., `202` for Resizable Plastic). Returns container index.
  * `color`: Optional 4-tuple of floats `(r, g, b, a)` where each value is between `0.0` and `1.0`.
  * `template`: Optional raw `saveObjects` dict to clone instead of the template pool.
* **`s.add_lua_chip(source, x=0.0, y=0.0, *, z=0.0005, inputs=None, outputs=None, variables=None, tps=30, priority=0, instruction_cost=1000, title="") -> int`**  
  Creates a Lua chip container. Returns container index.
  * `inputs`/`outputs`: Optional list of dicts, e.g. `[{"name": "target", "type": "entity", "value": optional_val}]`.
  * Types: `"entity"`, `"number"`, `"int"`, `"string"`, `"vector"`, `"array_entity"`, `"array_num"`, `"array_string"`, `"array_vec"`.
  * `variables`: Optional list of dicts defining persistent chip variables, e.g., `[{"name": "score", "value": 0.0}]`.
* **`s.add_ui_controller(controller, x=0.0, y=0.0) -> int`**  
  Adds a UI controller constructed via [`UIControllerBuilder`](file:///d:/程序/melonapk/MelonLuaSandbox/melon_lua/uicontrol_builder.py). Returns container index.
* **`s.connect(source, output_gate_or_target, target_or_input="", input_gate="", *, name="", start_point=(0.0, 0.0), end_point=(0.0, 0.0), output_group="", input_group="") -> dict`**  
  Wires a mechanic gate connection: `source` $\to$ `target`. Works in both modes. Returns the added constraint dict.
  * **Legacy Style (explicit indices):**
    `s.connect(source_idx, output_gate, target_idx, input_gate, ...)`
  * **ElementHandle Style (ergonomic):**
    `s.connect(element_handle, target_idx, input_gate, ...)`
    *Auto-resolves the element's primary output gate and GUID.*
* **`s.disconnect(source_idx, output_gate=None, target_idx=None, input_gate=None, *, wire_id=None) -> int`**  
  Removes matching connections. Returns deletion count.
* **`s.containers() -> list[dict]`**  
  Returns a list of all containers as `{idx, objectId, type, x, y}` dicts, where `type` is `"lua_chip"`, `"ui_controller"`, or `"item"`.
* **`s.save(out_path, *, write_icon=True) -> Path`**  
  Saves the state back to a `.melsave` file. Returns the resolved absolute path.

### Sandboxed Simulation Methods (Requires `load()` or `with` context)
* **`s.run_chip(source, *, ticks=1, inputs=None, chunk_name="@session_chip.lua", container_idx=None) -> dict`**  
  Compiles Lua code, calls `OnInit`, runs `ticks` ticks, and returns the final state: `{"outputs": {...}, "error": str|None}`.
* **`s.debug_run(source, *, ticks=1, inputs=None, chunk_name="@session_chip.lua", container_idx=None, stop_on_error=True, inputs_provider=None, reset_world=False) -> dict`**  
  Runs the chip and returns the entire frame-by-frame execution trace:
  ```python
  {
      "error": str | None,     # First fatal error encountered
      "outputs": {...},        # Final tick outputs
      "frames": [
          {
              "tick": 0, 
              "outputs": {...}, 
              "logs_delta": [("print", "...")], # Log level and message tuples
              "error": None, 
              "variables": {...}, 
              "entity_count": 3
          },
          ...
      ],
      "logs": [("print", "..."), ...] # Full console logs
  }
  ```
  * `inputs_provider`: Optional callable `f(tick_idx) -> dict` to feed dynamic inputs per-tick.
  * `reset_world`: wipe runtime-spawned entities and rebuild the world from the document before compiling. **Mandatory when the chip spawns objects** — otherwise each run accumulates the previous run's entities.
  * Frame phase contract: per tick `world.tick(dt)` (physics + sensors) runs FIRST, then `OnTick`. So `frames[0]` outputs = one world step + first OnTick (not the OnInit state). `OnInit` runs before frame 0 on the document state. A signal written in frame i's OnTick is readable by wires in frame i+1 (one-tick wire latency, matches the real device).
  * Input priority: host `inputs` (flat `{"enable": 1}` or bucketed `{"num": {"enable": 1}}`) **override scene wire values per gate name**; non-injected gates keep wire/default values.
* **`s.tick(inputs=None) -> dict`**  
  Drives one tick on the already-compiled chip (runs OnInit first if not done). Does *not* advance the Box2D physics world.
* **`s.run_ticks(ticks=1, *, inputs=None, inputs_provider=None, tick_callback=None, advance_world=True, stop_on_error=True) -> dict`**  
  Runs multiple ticks on the already-compiled chip.
* **`s.inspect(log_tail=50) -> dict`**  
  Returns a summary of the current sandbox state (`tick`, `elapsed`, `outputs`, `variables`, `entities`, `ropes`, `logs`, `error`) without advancing time.

### Entity & Physics Manipulation (Requires `load()` or `with` context)
* **`s.entities() -> list[dict]`**  
  Returns snapshots of all active physical entities. Each entry is:
  `{"entity_id": int, "local_id": int, "object_id": int, "name": str, "x": float, "y": float, "angle": float}`.
* **`s.get_entity(entity_id) -> Entity | None`**  
  Retrieves a live [`Entity`](file:///d:/程序/melonapk/MelonLuaSandbox/melon_lua/entity.py) object representing the physical body.
  * **Key Properties:** `e.position_x`, `e.position_y`, `e.angle`, `e.velocity_x`, `e.velocity_y`, `e.mass`, `e.gravity_scale`, `e.is_frozen`, `e.health`, `e.temperature`, `e.color_r`, `e.color_g`, `e.color_b`, `e.color_a`.
  * **Key Methods:**
    * `e.set_velocity(vx, vy)` (or `e.set_linear_velocity(vx, vy)`): Set linear velocity and syncs with physics body.
    * `e.get_velocity() -> tuple[float, float]`: Gets current physics-accurate velocity.
* **`s.spawn(name_or_id, x, y, **kw) -> Entity`**  
  Immediately spawns and returns an entity in the live simulation.
* **`s.remove(entity_id) -> bool`**  
  Deletes an entity from the world. Returns True if deleted.

### Ropes & Joints (Requires `load()` or `with` context)
* **`s.create_rope(from_id, to_id, kind="Simple", **params) -> int`**  
  Spawns a physical joint constraint between two entity IDs. Returns constraint ID.
  * `kind`: `"Simple"`, `"Spring"`, `"FixedDistance"`, `"FixedLine"`, `"Friction"`, `"Slider"`, `"Wheel"`, `"Relative"`, etc.
  * `params`: damping, distance, frequency, breakForce, etc.
* **`s.remove_rope(constraint_id) -> bool`**  
  Deletes a rope/joint. Returns True on success.

---

## 2. High-Level UI Building API (`UIControllerBuilder`)

[`UIControllerBuilder`](file:///d:/程序/melonapk/MelonLuaSandbox/melon_lua/uicontrol_builder.py) constructs interactive panels featuring buttons, sliders, joysticks, etc.

### Usage Example
```python
from melon_lua import MelsaveSession, UIControllerBuilder

ctrl = UIControllerBuilder()
# Using keyword arguments is recommended when name is omitted
fire_btn = ctrl.add_button(x=-150, y=100, text="FIRE")     
speed_sld = ctrl.add_slider(x=150, y=100, value=1.0, mn=0, mx=10)

s = MelsaveSession()
chip_idx = s.add_lua_chip(lua_src, x=3, y=0,
                           inputs=[{"name": "speed", "type": "number"},
                                   {"name": "fire", "type": "number"}])
ui_idx = s.add_ui_controller(ctrl, x=0, y=0)

# Connect UI outputs to Chip inputs (ElementHandle auto-routes gate name & GUID)
s.connect(fire_btn, chip_idx, "fire")
s.connect(speed_sld, chip_idx, "speed")

s.save("ui_control.melsave")
```

### Element Creation Methods
All methods return an `ElementHandle`.

> [!IMPORTANT]
> **Parameter Order Constraint:**
> Every builder method accepts **`name`** as its first positional parameter (e.g. `add_button(name="Button", x=0, y=0)`). 
> If you omit `name`, you **MUST** specify positional parameters with names (e.g., `x=10, y=20`). Calling `.add_button(10, 20)` is incorrect because Python maps `10` to `name` and `20` to `x`.

* **`.add_button(name="Button", x=0, y=0, text="", **kw)`** (Output gate: `"Button is down"`)
* **`.add_pedal(name="Pedal", x=0, y=0, text="", **kw)`** (Output gate: `"Button is down"`)
* **`.add_slider(name="Slider", x=0, y=0, value=0.0, mn=0.0, mx=1.0, integers_only=False, **kw)`** (Output gate: `"Value"`)
* **`.add_indicator(name="Indicator1", x=0, y=0, value=0.0, mn=0.0, mx=1.0, **kw)`** (Output gate: `"Value"`)
* **`.add_joystick(name="Joystick", x=0, y=0, multiplier=1.0, offset_angle=0.0, **kw)`** (Primary output gate: `"Joystick Direction"` (vector); also supports `"Joystick Angle"` (number), `"Joystick Activation"` (number))
* **`.add_toggle(name="Toggle", x=0, y=0, active=False, **kw)`** (Output gate: `"Value"`. Note: does *not* accept a `text` parameter)
* **`.add_rotation_wheel(name="SteeringWheel", x=0, y=0, value=0.0, limit=360.0, **kw)`** (Output gates: `"Angle Value"` (number), `"Up direction"` (vector))
* **`.add_steering_wheel(name="SteeringWheel", x=0, y=0, **kw)`** (Alias for `.add_rotation_wheel` with no default value/limit overrides)
* **`.add_input_field(name="InputField", x=0, y=0, **kw)`** (Output gates: `"Is changed"`, `"Field Value"`. Input gate: `"Label Color"`. Note: does *not* accept `default_text`)
* **`.add_pointer(name="Pointer", x=0, y=0, **kw)`** (Output gate: `"Dot worlds position"` (vector); also supports `"Dot viewport position"`, `"Dot screen position"`)
* **`.add_label(name="Label", x=0, y=0, value=0.0, **kw)`** (Displays a static/dynamic number via the slider family)
* **`.add_screen(name="Screen", x=0, y=0, active=True, **kw)`** (Anchor display panel showing a camera view)
* **`.add_custom_icon(name="CustomIcon", x=0, y=0, **kw)`** (Pure display icon element)

### ElementHandle Properties
* **`handle.group_id`** (GUID string): Uniquely identifies the UI element.
* **`handle.primary_output`** (string): The default output gate of this element type.
* **`handle.container_idx`** (int | None): The index of the UI Controller container in the session (bound during `add_ui_controller`).
* **`handle.gate(gate_name="")`**: Returns a tuple `(gate_name, group_id)` to target specific non-primary gates (e.g. `joy.gate("Joystick Angle")`).

---

## 3. Irreplaceable Query & Utility APIs

These standalone functions provide critical catalog data, schema information, and rendering functionality.

### Catalog & Schema Queries
* **`list_item_gates(item_name_or_id) -> dict`**  
  Queries the input and output gates of a catalog item. Essential for finding gate names.
  ```python
  from melon_lua import list_item_gates
  print(list_item_gates("ScreenTextDevice")) 
  # Returns {"inputs": [{"key": "string", "data_name": "text", ...}], "outputs": [...]}
  ```
* **`element_schema(element_type="") -> dict`**  
  Queries the input and output gates of a UI element. Pass empty string `""` to list all available UI types.
  ```python
  from melon_lua import element_schema
  print(element_schema("slider"))
  ```
* **`object_id_for_name(name) -> Optional[int]`**  
  Resolves an item's catalog name to its numeric object ID (e.g., `"ResizablePlastic"` $\to$ `202`). Returns `None` if unresolved.

### Visualization (Preview Renders)
* **`render_world(world, out_path, *, width=640, height=480, ppm=96.0, center_x=0.0, center_y=0.5, show_grid=True, show_labels=True, fit_to_content=False, focus_rect=None, scale=1.0) -> Path`**  
  Renders the current physics world state to a PNG file. Use this for visual checks during test execution. All parameters after `out_path` are keyword-only.
  * `focus_rect`: Optional 4-tuple of floats `(x0, y0, x1, y1)` in world coordinates to zoom into a specific area.
  ```python
  from melon_lua import render_world
  # Access the live world from the session
  render_world(s.world, "debug_preview.png", fit_to_content=True)
  ```

### Raw Document Access
* **`read_melsave(path) -> MelsaveDocument`**  
  Reads a `.melsave` file and returns a `MelsaveDocument` dataclass instance.
  * To get the raw JSON structure without initializing a session, access: `read_melsave(path).raw_data` (dict).t.
