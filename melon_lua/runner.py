"""MelonScriptRunner — melon Lua chip execution engine.

Loads the real LuaPreamble.lua (388 lines, copied verbatim from APK assetbundle),
registers all C# backend modules, drives the OnInit/OnTick/OnSpawned lifecycle
at a configurable TPS rate, and bridges typed inputs/outputs sub-tables.
"""
import importlib.resources as _resources
import time as _time
from typing import Any, Callable, Optional

from lupa import LuaRuntime, LuaError

from .world import WorldContext
from .backend import register_all
from .stdlib_melon import apply_melon_stdlib


# Sentinel for "function was not defined by user"
_UNDEFINED = object()


class MelonScriptRunner:
    """One runner = one Lua VM = one chip session."""

    def __init__(
        self,
        tps: float = 20.0,
        max_instructions: int = 100000,
        world: Optional[WorldContext] = None,
        quiet: bool = False,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.tps = float(tps)
        self.max_instructions = int(max_instructions)
        self.world = world or WorldContext()
        self.quiet = quiet
        self._log_callback = log_callback

        self._lua = LuaRuntime(unpack_returned_tuples=True)
        self._g = self._lua.globals()

        # Lifecycle flags
        self._compiled = False
        self._last_error: Optional[str] = None
        self._has_on_init = False
        self._has_on_tick = False
        self._has_on_activated = False
        self._has_on_deactivated = False
        self._has_on_destroy = False
        self._has_on_spawned = False
        self._on_init_called = False

        self._setup_sandbox()
        self._register_backends()
        self._load_preamble()

    # ===== Setup =====

    def _setup_sandbox(self):
        """Match melon LuaSandboxConfigBase: std libs + strip dangerous globals.

        See lua-triage/MELON_LUA_STDLIB.md (APK LuaSandboxConfig + ApiReference).
        """
        apply_melon_stdlib(self._lua, self._g)

    def _load_preamble(self):
        """Load the real LuaPreamble.lua bundled with this package."""
        try:
            preamble_src = (_resources.files(__package__)
                            / "preamble.lua").read_text(encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"failed to load preamble.lua: {e}") from e

        try:
            self._lua.execute(preamble_src)
        except LuaError as e:
            raise RuntimeError(f"preamble failed: {e}") from e

    def _register_backends(self):
        register_all(
            self._lua, self._g, self.world,
            on_log=self._on_log if not self.quiet else None,
            queue_spawn_result=None,
        )

    def _sync_chip_env(self):
        env = self._lua.table_from({})
        if self._g["OnSpawned"] is not None:
            env["OnSpawned"] = self._g["OnSpawned"]
        self._g["__current_env"] = env

    def _flush_spawn_pipeline(self):
        if not self._compiled:
            return
        results = self.world.spawn_queue.flush()
        if not results:
            return
        self._sync_chip_env()
        dispatch = self._g["__dispatch_spawn"]
        if dispatch is None:
            return
        for req_id, ent_ids in results:
            try:
                dispatch(req_id, self._lua.table_from(list(ent_ids)))
            except LuaError as e:
                self._last_error = str(e)

    def _on_log(self, level: str, msg: str):
        if self._log_callback:
            self._log_callback(level, msg)
        else:
            tag = {"print": "", "warn": "[warn] ", "error": "[error] "}.get(level, "")
            print(f"{tag}{msg}")

    # ===== Compilation =====

    def compile(self, source: str, chunk_name: str = "@chip.lua") -> bool:
        """Compile + execute the chunk once. Captures OnInit/OnTick/etc defs."""
        self._last_error = None
        try:
            # Wrap source so we get a meaningful chunk label in errors
            wrapped = f"--{chunk_name}\n" + source
            self._lua.execute(wrapped)

            self._has_on_init = self._g["OnInit"] is not None
            self._has_on_tick = self._g["OnTick"] is not None
            self._has_on_activated = self._g["OnActivated"] is not None
            self._has_on_deactivated = self._g["OnDeactivated"] is not None
            self._has_on_destroy = self._g["OnDestroy"] is not None
            self._has_on_spawned = self._g["OnSpawned"] is not None
            self._sync_chip_env()

            self._compiled = True
            return True
        except LuaError as e:
            self._last_error = str(e)
            self._compiled = False
            return False
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            self._compiled = False
            return False

    # ===== Typed I/O =====

    def set_inputs(self, inputs: dict[str, dict[str, Any]]):
        """Replace the `inputs` table. Structure:
            {
              "num":   {"speed": 1.5, ...},
              "int":   {"count": 3, ...},
              "string":{"label": "ok", ...},
              "vec":   {"direction": {"x":1,"y":0,"z":0,"w":0}, ...},
              "color": {"tint": {"r":1,"g":0,"b":0,"a":1}, ...},
              "entity":{"target": 42, ...},
              "array_num":    {"data": [1, 2, 3], ...},
              "array_string": {"names": ["a","b"], ...},
              "array_vec":    {"points": [{"x":0,"y":0,"z":0,"w":0}, ...], ...},
              "array_entity": {"targets": [1, 2, 3], ...},
            }
        Every sub-table ALWAYS exists in the real game (nil-safe).
        """
        # Build the typed inputs table in Lua
        sub_categories = ("num", "int", "string", "vec", "color", "entity",
                          "array_num", "array_string", "array_vec", "array_entity")
        inputs_tbl = self._lua.table_from({})
        for cat in sub_categories:
            sub_data = (inputs or {}).get(cat, {}) or {}
            sub_tbl = self._lua.table_from({})
            for k, v in sub_data.items():
                if isinstance(v, dict):
                    sub_tbl[k] = self._lua.table_from(v)
                elif isinstance(v, list):
                    # array_* categories: lists of values or dicts
                    if v and isinstance(v[0], dict):
                        items = [self._lua.table_from(item) for item in v]
                        sub_tbl[k] = self._lua.table_from(items)
                    else:
                        sub_tbl[k] = self._lua.table_from(list(v))
                else:
                    sub_tbl[k] = v
            inputs_tbl[cat] = sub_tbl
        self._g["inputs"] = inputs_tbl

        # Always-fresh outputs table
        outputs_tbl = self._lua.table_from({})
        for cat in sub_categories:
            outputs_tbl[cat] = self._lua.table_from({})
        self._g["outputs"] = outputs_tbl

    def get_outputs(self) -> dict[str, dict[str, Any]]:
        """Return outputs as a plain Python dict."""
        result: dict[str, dict[str, Any]] = {}
        try:
            outputs = self._g["outputs"]
            if outputs is None:
                return result
            for cat in outputs.keys():
                cat_tbl = outputs[cat]
                if cat_tbl is None:
                    continue
                cat_dict: dict[str, Any] = {}
                for key in cat_tbl.keys():
                    val = cat_tbl[key]
                    cat_dict[str(key)] = self._unwrap(val)
                result[str(cat)] = cat_dict
        except Exception:
            pass
        return result

    @staticmethod
    def _unwrap(val: Any) -> Any:
        """Recursively unwrap lupa tables to Python containers."""
        if val is None or isinstance(val, (bool, int, float, str)):
            return val
        if hasattr(val, "keys"):
            try:
                keys = list(val.keys())
                if keys and all(isinstance(k, int) for k in keys):
                    return [MelonScriptRunner._unwrap(val[k]) for k in sorted(keys)]
                d = {}
                for k in keys:
                    d[str(k)] = MelonScriptRunner._unwrap(val[k])
                return d
            except Exception:
                return str(val)
        return val

    # ===== Lifecycle =====

    def call_on_init(self):
        if not self._compiled or not self._has_on_init or self._on_init_called:
            return
        if self._g["outputs"] is None:
            self.set_inputs({})
        try:
            self._g["OnInit"]()
            self._on_init_called = True
            self._sync_chip_env()
            self._flush_spawn_pipeline()
        except LuaError as e:
            self._last_error = str(e)

    def call_on_activated(self):
        if not self._compiled or not self._has_on_activated:
            return
        try:
            self._g["OnActivated"]()
        except LuaError as e:
            self._last_error = str(e)

    def call_on_deactivated(self):
        if not self._compiled or not self._has_on_deactivated:
            return
        try:
            self._g["OnDeactivated"]()
        except LuaError as e:
            self._last_error = str(e)

    def call_on_destroy(self):
        if not self._compiled or not self._has_on_destroy:
            return
        try:
            self._g["OnDestroy"]()
        except LuaError as e:
            self._last_error = str(e)

    def run_tick(self, inputs: Optional[dict] = None) -> dict:
        """Drive one tick: flush signals, run OnTick, return outputs+error."""
        if not self._compiled:
            return {"error": self._last_error or "not compiled", "outputs": {}}

        if inputs is not None:
            self.set_inputs(inputs)
        elif self._g["inputs"] is None:
            self.set_inputs({})

        # __flush_signals runs deferred signals at start of tick
        try:
            flush = self._g["__flush_signals"]
            if flush is not None:
                flush()
        except LuaError:
            pass

        if self._has_on_tick:
            try:
                self._g["OnTick"]()
            except LuaError as e:
                self._last_error = str(e)
                return {"error": str(e), "outputs": self.get_outputs()}

        self._flush_spawn_pipeline()

        return {"error": None, "outputs": self.get_outputs()}

    def queue_spawn_result(self, request_id: int, entity_ids: list[int]):
        """Host: external spawn completed — fire OnSpawned like the game engine."""
        self.world.spawn_requests[request_id] = list(entity_ids)
        self._sync_chip_env()
        dispatch = self._g["__dispatch_spawn"]
        if dispatch is not None:
            try:
                dispatch(request_id, self._lua.table_from(list(entity_ids)))
            except LuaError as e:
                self._last_error = str(e)

    # ===== Dispatch (collision/trigger/wire events from host) =====

    def dispatch_collision(self, cb_id: int, other_id: int, self_id: int,
                           nx: float = 0.0, ny: float = 0.0):
        """Host injects a collision event. Sets the __cb_* globals then calls
        __dispatch_collision (defined in LuaPreamble.lua)."""
        self._g["__cb_id"] = cb_id
        self._g["__cb_other"] = other_id
        self._g["__cb_self"] = self_id
        self._g["__cb_nx"] = nx
        self._g["__cb_ny"] = ny
        try:
            fn = self._g["__dispatch_collision"]
            if fn: fn()
        except LuaError as e:
            self._last_error = str(e)

    def dispatch_trigger(self, cb_id: int, other_id: int, self_id: int):
        self._g["__cb_id"] = cb_id
        self._g["__cb_other"] = other_id
        self._g["__cb_self"] = self_id
        try:
            fn = self._g["__dispatch_trigger"]
            if fn: fn()
        except LuaError as e:
            self._last_error = str(e)

    def dispatch_wire_connected(self, cb_id: int, self_id: int, input_key: str,
                                output_entity_id: int, output_key: str):
        self._g["__cb_id"] = cb_id
        self._g["__cb_self"] = self_id
        self._g["__cb_input_key"] = input_key
        self._g["__cb_output_entity"] = output_entity_id
        self._g["__cb_output_key"] = output_key
        try:
            fn = self._g["__dispatch_wire_connected"]
            if fn: fn()
        except LuaError as e:
            self._last_error = str(e)

    def dispatch_wire_disconnected(self, cb_id: int, self_id: int, input_key: str):
        self._g["__cb_id"] = cb_id
        self._g["__cb_self"] = self_id
        self._g["__cb_input_key"] = input_key
        try:
            fn = self._g["__dispatch_wire_disconnected"]
            if fn: fn()
        except LuaError as e:
            self._last_error = str(e)

    # ===== Run loop =====

    def run_loop(self, duration: Optional[float] = 5.0, *,
                 ticks: Optional[int] = None,
                 tick_callback: Optional[Callable[[int, float, dict], None]] = None,
                 inputs_provider: Optional[Callable[[int], dict]] = None):
        """Run the chip.

        Pass either `duration` (seconds) or `ticks` (raw tick count).
        If both are given, `ticks` wins.
        """
        dt = 1.0 / self.tps
        if ticks is not None:
            total_ticks = int(ticks)
        else:
            total_ticks = int((duration or 0.0) * self.tps)

        # First-tick bootstrap
        self.call_on_init()
        self.call_on_activated()

        for i in range(total_ticks):
            self.world.tick(dt)
            inputs = inputs_provider(i) if inputs_provider else None
            result = self.run_tick(inputs)
            if tick_callback:
                tick_callback(i, dt, result)
            if result.get("error"):
                self._on_log("error", f"[tick {i}] {result['error']}")
            _time.sleep(0)  # yield, don't actually sleep

        self.call_on_deactivated()
        self.call_on_destroy()

    # ===== Accessors =====

    @property
    def has_on_tick(self) -> bool: return self._has_on_tick
    @property
    def has_on_init(self) -> bool: return self._has_on_init
    @property
    def has_on_activated(self) -> bool: return self._has_on_activated
    @property
    def has_on_spawned(self) -> bool: return self._has_on_spawned
    @property
    def last_error(self) -> Optional[str]: return self._last_error

    @property
    def logs(self) -> list[tuple[str, str]]:
        return list(self.world.console_buffer)

    def clear_logs(self):
        self.world.console_buffer.clear()
