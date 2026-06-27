"""Unified session: one .melsave = one session, document as source of truth.

A `MelsaveSession` binds a .melsave file (or an empty world) and provides both
document-level operations (add items, add Lua chips, wire gates, save) and
runtime operations (compile/run Lua chips, physics, spawn entities). The
parsed Data dict is the single source of truth; runtime is lazy — only
activated when `.load()` is called (or via context manager).

Two modes:

- **Document mode** (default after construction): the parsed Data dict is ready.
  All document operations work: ``add_item``, ``add_lua_chip``, ``connect``,
  ``disconnect``, ``containers``, ``save``.
- **Runtime mode** (after ``.load()`` or ``with ... as s:``): Box2D world + Lua
  runner are initialized. Runtime operations work: ``run_chip``, ``tick``,
  ``spawn``, ``create_rope``, ``snapshot``.

Example (document only)::

    s = MelsaveSession()                    # empty world, document mode
    s.add_item(202, x=0, y=0)
    s.add_lua_chip(src, x=2, y=0, inputs=[...])
    s.connect(0, "entity", 1, "target")
    s.save("out.melsave")

Example (with runtime)::

    with MelsaveSession("save.melsave") as s:   # loads doc + starts runtime
        s.run_chip(chip_src, ticks=100)
        print(s.snapshot())
        s.save("modified.melsave")
"""
from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any, Optional

from .melsave import MelsaveDocument, read_melsave, spawn_document_into_world
from .melsave_writer import (
    write_melsave,
    write_world_to_melsave,
    build_diff_from_world,
    connect_gates,
    disconnect_gates,
    list_gate_connections,
    MECHANIC_CONSTRAINT_ID,
)
from .world import WorldContext
from .runner import MelonScriptRunner

# Packaged empty world template — minimal valid save with zero objects.
_EMPTY_TEMPLATE = Path(__file__).parent / "data" / "empty.melsave"


class MelsaveSession:
    """One session = one save file (document) + optional runtime (world + runner).

    Construction immediately reads the .melsave into an in-memory Data dict
    (document mode). Calling ``.load()`` or entering a ``with`` block also
    starts the runtime (Box2D world + Lua VM).

    Document operations (add_item, add_lua_chip, connect, save, ...) never
    require the runtime. Runtime operations (run_chip, tick, spawn,
    create_rope, snapshot, ...) require the runtime — they raise if not loaded.
    """

    def __init__(
        self,
        melsave_path: str | Path | None = None,
        *,
        tps: float = 20.0,
        quiet: bool = True,
        app_version: str = "36.0",
        map_name: str = "Default",
    ):
        """Create a session.

        Args:
            melsave_path: Path to a .melsave file. If None, an empty world
                template is used (session starts with zero containers).
            tps: Default ticks-per-second for the Lua runner.
            quiet: Suppress runner stdout.
            app_version: appVersion written to MetaData (used for empty/new saves).
            map_name: mapName written to MetaData.
        """
        self.tps = float(tps)
        self._quiet = bool(quiet)

        # Document (always ready after __init__)
        if melsave_path is None:
            self.melsave_path: Optional[Path] = None
            self._doc: MelsaveDocument = self._build_empty_document(
                app_version=app_version, map_name=map_name
            )
        else:
            self.melsave_path = Path(melsave_path)
            self._doc = read_melsave(self.melsave_path)

        # Runtime (lazy — None until load())
        self._world: Optional[WorldContext] = None
        self._runner: Optional[MelonScriptRunner] = None
        self._runtime_active = False

        # Meta overrides for new/empty sessions
        self._meta_overrides: dict[str, Any] = {}
        if melsave_path is None:
            self._meta_overrides = {
                "appVersion": app_version,
                "mapName": map_name,
            }
        self._icon: Optional[bytes] = None

        # Track which pending chip (by container index) the last run_chip()
        # compiled, so the source can be synced before save.
        self._active_chip_container: Optional[int] = None

    # ==================================================================
    # Construction helpers
    # ==================================================================

    @classmethod
    def create_empty(cls, **kw: Any) -> "MelsaveSession":
        """Create a session backed by an empty world.

        Equivalent to ``MelsaveSession()`` but makes intent explicit.
        """
        return cls(None, **kw)

    def _build_empty_document(
        self, *, app_version: str = "36.0", map_name: str = "Default"
    ) -> MelsaveDocument:
        """Build a minimal empty MelsaveDocument for from-scratch sessions."""
        meta = {
            "UniqueId": "",
            "icon": {"AssetId": "Icon", "CanBeNull": False},
            "metadata": {"ManifestId": "", "Name": ""},
            "versionId": 7,
            "appVersion": app_version,
            "mapName": map_name,
            "CustomMapChangesVersion": 0,
            "seed": -1,
            "timeScale": 1.0,
            "category": "video",
            "CategoryValidated": "video",
        }
        data = {"saveObjectContainers": []}
        return MelsaveDocument(
            path="",
            save_name="",
            category="video",
            app_version=app_version,
            version_id=7,
            map_name=map_name,
            object_count=0,
            objects=[],
            metadata=meta,
            data_extras={},
            raw_data=data,
        )

    # ==================================================================
    # Lifecycle / context manager
    # ==================================================================

    def load(self) -> "MelsaveSession":
        """Start the runtime: spawn document objects into a Box2D world and
        build the Lua runner. Idempotent.

        After ``load()``, runtime operations (``run_chip``, ``tick``,
        ``spawn``, ``create_rope``, ``snapshot``) are available.
        """
        if self._runtime_active:
            return self
        self._world = WorldContext()
        spawn_document_into_world(self._doc, self._world)
        self._runner = MelonScriptRunner(
            tps=self.tps,
            world=self._world,
            quiet=self._quiet,
        )
        # Load existing mechanic gate wires from the document's constraints
        self._load_gate_wires_from_doc()
        self._runtime_active = True
        return self

    def _load_gate_wires_from_doc(self) -> None:
        """Populate ``world.gate_wires`` from the document's raw constraints."""
        assert self._world is not None
        first = True
        for obj in self._doc.objects:
            raw = getattr(obj, "raw", None) or {}
            cs = raw.get("constraints")
            if not isinstance(cs, list) or not cs:
                continue
            self._world.gate_wires.from_constraint_dicts(cs, append=not first)
            first = False

    def close(self) -> None:
        """Release the Box2D world and Lua VM. Idempotent."""
        if self._world is not None:
            self._world.b2_world = None
            self._world._b2_bodies.clear()
            self._world._b2_joints.clear()
        self._runner = None
        self._world = None
        self._runtime_active = False

    def __enter__(self) -> "MelsaveSession":
        return self.load()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ==================================================================
    # Document mode: containers
    # ==================================================================

    @property
    def container_count(self) -> int:
        """Number of containers in the document."""
        containers = self._doc.raw_data.get("saveObjectContainers") or []
        return len(containers)

    def containers(self) -> list[dict]:
        """List all containers as ``{idx, objectId, type, x, y}`` dicts."""
        out: list[dict] = []
        for i, c in enumerate(self._raw_containers()):
            so = c.get("saveObjects") or {}
            oid = so.get("objectId", 0)
            pos = so.get("position") or {}
            kind = "lua_chip" if oid == 507707712 else (
                "ui_controller" if oid == 2046689600 else "item"
            )
            out.append({
                "idx": i,
                "objectId": oid,
                "type": kind,
                "x": pos.get("x", 0),
                "y": pos.get("y", 0),
            })
        return out

    def get_container(self, idx: int) -> dict:
        """Return the raw saveObjects dict for container ``idx``."""
        containers = self._raw_containers()
        if idx < 0 or idx >= len(containers):
            raise IndexError(f"container index {idx} out of range ({len(containers)})")
        return containers[idx].get("saveObjects") or {}

    def add_container(self, save_objects: dict) -> int:
        """Append a raw container (pre-built saveObjects dict).

        Returns the new container index.
        """
        idx = self.container_count
        self._raw_containers().append({
            "saveObjects": save_objects,
            "saveObjectChildren": [],
        })
        return idx

    def add_item(
        self,
        object_id: int,
        x: float = 0.0,
        y: float = 0.0,
        *,
        z: float = -0.0005,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        color: tuple[float, float, float, float] | None = None,
        dynamic: bool = True,
        freezed: bool = False,
        template: dict | None = None,
    ) -> int:
        """Add a spawnable item (plastic, engine, rocket body, ...).

        Args:
            object_id: Melon objectId (e.g. 202 = ResizablePlastic, 132 = engine).
            x, y: World position.
            color: RGBA tuple (0-1), or None for default.
            dynamic: If True, gravity affects the object.
            freezed: If True, object is frozen in place.
            template: Optional raw saveObjects dict to clone instead of
                loading from the template pool.

        Returns:
            Container index (use for connect references).
        """
        from .melsave_builder import _build_item_save_objects
        so = _build_item_save_objects(
            object_id, x, y, z=z, rotation=rotation,
            scale_x=scale_x, scale_y=scale_y,
            color=color, dynamic=dynamic, freezed=freezed,
            template=template,
        )
        return self.add_container(so)

    def add_lua_chip(
        self,
        source: str,
        x: float = 0.0,
        y: float = 0.0,
        *,
        z: float = 0.0005,
        inputs: list[dict] | None = None,
        outputs: list[dict] | None = None,
        variables: list[dict] | None = None,
        tps: int = 30,
        priority: int = 0,
        instruction_cost: int = 1000,
        title: str = "",
    ) -> int:
        """Add a Lua chip container to the document.

        Also marks it as the active chip so subsequent ``run_chip()`` calls
        (without ``container_idx``) will sync source changes.

        Args:
            source: Lua source code (must define OnTick at minimum).
            x, y: World position.
            inputs: List of ``{"name": str, "type": str, "value": ...}`` dicts.
            outputs: Same format as inputs.
            variables: List of ``{"name": str, "value": float}``.
            tps: Ticks per second.
            title: Visual title shown on the chip.

        Returns:
            Container index.
        """
        from .melsave_builder import _build_chip_save_objects
        so = _build_chip_save_objects(
            source, x, y, z=z,
            inputs=inputs, outputs=outputs, variables=variables,
            tps=tps, priority=priority, instruction_cost=instruction_cost,
            title=title,
        )
        idx = self.add_container(so)
        self._active_chip_container = idx
        return idx

    def add_ui_controller(self, controller: Any, x: float = 0.0, y: float = 0.0) -> int:
        """Add a UI controller (objectId=2046689600).

        Args:
            controller: A UIControllerBuilder with elements added.
            x, y: World position.

        Returns:
            Container index.
        """
        so = controller.build_save_object(x=x, y=y)
        return self.add_container(so)

    # ==================================================================
    # Document mode: gate wires (unified API)
    # ==================================================================

    def connect(
        self,
        source_idx: int,
        output_gate: str,
        target_idx: int,
        input_gate: str,
        *,
        name: str = "",
        start_point: tuple[float, float] = (0.0, 0.0),
        end_point: tuple[float, float] = (0.0, 0.0),
    ) -> dict:
        """Wire a mechanic gate connection: ``source.output`` → ``target.input``.

        The connection is stored on the source object's ``constraints`` list.
        Works in both document and runtime modes. In runtime mode, also
        registers the wire in the live ``GateWireRegistry``.

        Args:
            source_idx: Container index of the source (output) object.
            output_gate: Output gate name on the source (e.g. "entity").
            target_idx: Container index of the target (input) object.
            input_gate: Input gate name on the target (e.g. "target").
            name: Optional display name for the connection.
            start_point: Visual offset of the source port (local space).
            end_point: Visual offset of the target port (local space).

        Returns:
            The constraint dict that was added.
        """
        result = connect_gates(
            self._doc.raw_data, source_idx, output_gate, target_idx, input_gate,
            name=name, start_point=start_point, end_point=end_point,
        )
        # If runtime is active, also register in the live registry so
        # save() picks it up via the registry-as-source-of-truth path.
        if self._runtime_active and self._world is not None:
            self._world.gate_wires.connect(
                source_idx, output_gate, target_idx, input_gate,
                name=name, start_point=start_point, end_point=end_point,
            )
        return result

    def disconnect(
        self,
        source_idx: int,
        output_gate: str | None = None,
        target_idx: int | None = None,
        input_gate: str | None = None,
        *,
        wire_id: int | None = None,
    ) -> int:
        """Remove mechanic gate connections.

        If ``wire_id`` is given, removes that specific wire (runtime mode only).
        Otherwise removes all connections from ``source_idx`` matching the
        optional filters (output_gate / target_idx / input_gate).

        Returns the number of connections removed.
        """
        if wire_id is not None:
            if not self._runtime_active or self._world is None:
                raise RuntimeError(
                    "wire_id disconnect requires runtime; call .load() first"
                )
            return 1 if self._world.gate_wires.disconnect(wire_id) else 0
        # Document-level disconnect
        removed = disconnect_gates(
            self._doc.raw_data, source_idx,
            output_gate=output_gate, target_idx=target_idx, input_gate=input_gate,
        )
        # Also clean from live registry if active
        if self._runtime_active and self._world is not None and removed > 0:
            self._world.gate_wires.disconnect_matching(
                source_idx=source_idx,
                target_idx=target_idx,
                output_gate=output_gate,
                input_gate=input_gate,
            )
        return removed

    def list_connections(self, container_idx: int | None = None) -> list[dict]:
        """List all mechanic gate connections.

        Args:
            container_idx: If given, only list connections from this source.

        Each result: ``{source_idx, target_idx, output_gate, input_gate, name}``.
        """
        return list_gate_connections(self._doc.raw_data, container_idx)

    # ==================================================================
    # Document mode: meta / icon
    # ==================================================================

    def set_meta(self, **kwargs: Any) -> None:
        """Override MetaData fields (appVersion, mapName, seed, ...)."""
        self._meta_overrides.update(kwargs)

    def set_icon(self, icon_bytes: bytes) -> None:
        """Set the save icon (PNG bytes)."""
        self._icon = icon_bytes

    def load_icon_from(self, path: str | Path) -> None:
        """Load icon from a .png file."""
        self._icon = Path(path).read_bytes()

    # ==================================================================
    # Runtime mode: chip execution
    # ==================================================================

    def run_chip(
        self,
        source: str,
        *,
        ticks: int = 1,
        inputs: Optional[dict] = None,
        chunk_name: str = "@session_chip.lua",
        container_idx: Optional[int] = None,
    ) -> dict:
        """Compile a Lua chip and run it for ``ticks`` ticks.

        If ``ticks == 0``, only compiles + calls OnInit. If ``ticks >= 1``,
        OnInit runs first, then OnTick runs ``ticks`` times.

        Args:
            container_idx: If given, sync the source back into that chip
                container so it persists on ``save()``. Chips created via
                ``add_lua_chip()`` auto-sync; pass the index to keep edits live.
        """
        self._require_runtime()
        assert self._runner is not None
        r = self._runner
        if not r.compile(source, chunk_name=chunk_name):
            return {"error": r.last_error or "compile failed", "outputs": {}}
        idx = container_idx if container_idx is not None else self._active_chip_container
        if idx is not None:
            self._sync_chip_source(idx, source)
        r.call_on_init()
        if ticks <= 0:
            return {"error": None, "outputs": r.get_outputs()}
        if ticks == 1:
            return r.run_tick(inputs=inputs)
        provider = (lambda i: inputs) if inputs is not None else None
        r.run_loop(ticks=ticks, inputs_provider=provider)
        return {"error": r.last_error, "outputs": r.get_outputs()}

    def _sync_chip_source(self, container_idx: int, source: str) -> None:
        """Update the lua_chip_source metadata of a chip container."""
        so = self.get_container(container_idx)
        for sm in so.get("saveMetaDatas", []):
            if sm.get("key") == "lua_chip_source":
                sm["stringValue"] = source
                return

    def compile_only(self, source: str, chunk_name: str = "@session_chip.lua") -> bool:
        """Compile a chip without running. Returns True on success."""
        self._require_runtime()
        assert self._runner is not None
        return self._runner.compile(source, chunk_name=chunk_name)

    def tick(self, inputs: Optional[dict] = None) -> dict:
        """Run a single OnTick on the already-compiled chip."""
        self._require_runtime()
        assert self._runner is not None
        return self._runner.run_tick(inputs=inputs)

    # ==================================================================
    # Runtime mode: entity / world access
    # ==================================================================

    @property
    def world(self) -> WorldContext:
        self._require_runtime()
        assert self._world is not None
        return self._world

    @property
    def runner(self) -> MelonScriptRunner:
        self._require_runtime()
        assert self._runner is not None
        return self._runner

    @property
    def document(self) -> MelsaveDocument:
        return self._doc

    def entities(self) -> list[dict]:
        """Snapshot list of alive entities."""
        self._require_runtime()
        assert self._world is not None
        out = []
        for e in self._world.entities.values():
            if not getattr(e, "alive", True):
                continue
            out.append({
                "entity_id": e.entity_id,
                "local_id": e.local_id,
                "object_id": e.object_id,
                "name": e.name,
                "x": float(e.position_x),
                "y": float(e.position_y),
                "angle": float(e.angle),
            })
        return out

    def get_entity(self, entity_id: int):
        if self._world is None:
            return None
        return self._world.get_entity(entity_id)

    def spawn(self, name_or_id, x: float = 0.0, y: float = 0.0, **kw):
        """Spawn a new entity into the world. Returns the Entity."""
        self._require_runtime()
        assert self._world is not None
        return self._world.spawn_entity(name_or_id, x, y, **kw)

    def remove(self, entity_id: int) -> bool:
        """Remove an entity. Returns True if it existed."""
        self._require_runtime()
        assert self._world is not None
        e = self._world.entities.get(entity_id)
        if e is None:
            return False
        self._world.remove_entity(entity_id)
        return True

    # ==================================================================
    # Runtime mode: ropes / constraints
    # ==================================================================

    def create_rope(
        self,
        from_id: int,
        to_id: int,
        kind: str | int = "Simple",
        **params,
    ) -> int:
        """Create a rope/constraint between two entities."""
        self._require_runtime()
        assert self._world is not None
        return self._world.create_rope(from_id, to_id, kind, **params)

    def remove_rope(self, constraint_id: int) -> bool:
        """Remove a rope and its Box2D joint."""
        self._require_runtime()
        assert self._world is not None
        return self._world.destroy_rope(constraint_id)

    def set_rope_param(self, constraint_id: int, key: str, value) -> bool:
        self._require_runtime()
        assert self._world is not None
        return self._world.set_rope_param(constraint_id, key, value)

    def ropes(self) -> list[dict]:
        """List all physical constraints in the registry."""
        self._require_runtime()
        assert self._world is not None
        reg = self._world.constraints
        from .constraints import KIND_IDS
        out = []
        for cid, c in reg._constraints.items():
            out.append({
                "id": cid,
                "kind_id": c.constraint_id,
                "kind": KIND_IDS.get(c.constraint_id, "Unknown"),
                "start_local_id": c.start_object_id,
                "end_local_id": c.end_object_id,
                "distance": c.distance,
            })
        return out

    # ==================================================================
    # Runtime mode: snapshot / diff
    # ==================================================================

    def snapshot(self) -> dict:
        """Return a serializable snapshot of the current world state."""
        self._require_runtime()
        assert self._world is not None
        w = self._world
        return {
            "tick": w.current_tick,
            "elapsed": w.elapsed_time,
            "entities": self.entities(),
            "ropes": self.ropes(),
            "variables": dict(w.chip_variables),
            "entity_count": sum(
                1 for e in w.entities.values() if getattr(e, "alive", True)
            ),
        }

    def diff(self) -> dict:
        """Return the WorldDiff as a plain dict (for inspection)."""
        self._require_runtime()
        assert self._world is not None
        d = build_diff_from_world(self._world, self._doc)
        return {
            "modified": {str(k): v for k, v in d.modified_objects.items()},
            "added_count": len(d.added_objects),
            "removed": sorted(d.removed_local_ids),
            "constraint_lids": sorted(d.modified_constraints.keys()),
        }

    # ==================================================================
    # Export (works in both modes)
    # ==================================================================

    def save(
        self,
        out_path: str | Path,
        *,
        write_icon: bool = True,
    ) -> Path:
        """Write the current document to a .melsave file.

        In document mode, serializes the in-memory Data dict directly.
        In runtime mode, first applies world-state changes (positions,
        ropes, spawned entities) via diff, then merges gate wires.

        Returns the resolved absolute path of the written file.
        """
        if self._runtime_active and self._world is not None:
            return self._save_with_runtime(out_path, write_icon=write_icon)
        return self._save_document_only(out_path, write_icon=write_icon)

    def _save_document_only(
        self, out_path: str | Path, *, write_icon: bool = True
    ) -> Path:
        """Serialize the in-memory Data dict (document mode)."""
        meta = copy.deepcopy(self._doc.metadata) if isinstance(self._doc.metadata, dict) else {}
        meta.update(self._meta_overrides)
        if not meta.get("UniqueId"):
            meta["UniqueId"] = str(uuid.uuid4())
        data = copy.deepcopy(self._doc.raw_data)
        icon = self._icon if write_icon else None
        if icon is None and write_icon and self.melsave_path is not None:
            icon = self._read_icon_from_path(self.melsave_path)
        return Path(
            write_melsave(out_path, data, meta, icon)
        ).resolve()

    def _save_with_runtime(
        self, out_path: str | Path, *, write_icon: bool = True
    ) -> Path:
        """Apply world diff + gate wires, then write (runtime mode)."""
        assert self._world is not None
        # Sync active chip source before diff
        p = write_world_to_melsave(
            self._world,
            self._doc,
            out_path,
            write_icon=write_icon,
        )
        return Path(p).resolve()

    def _read_icon_from_path(self, path: Path) -> Optional[bytes]:
        """Try to read the Icon entry from a .melsave."""
        try:
            import zipfile as _zf
            with _zf.ZipFile(path, "r") as zf:
                if "Icon" in zf.namelist():
                    return zf.read("Icon")
        except Exception:
            pass
        return None

    # save_as is an alias for backward compatibility
    save_as = save

    # ==================================================================
    # Logs / errors
    # ==================================================================

    @property
    def logs(self) -> list:
        if not self._runtime_active or self._runner is None:
            return []
        return self._runner.logs

    @property
    def last_error(self) -> Optional[str]:
        if not self._runtime_active or self._runner is None:
            return None
        return self._runner.last_error

    @property
    def outputs(self) -> dict:
        if not self._runtime_active or self._runner is None:
            return {}
        return self._runner.get_outputs()

    # ==================================================================
    # Backward-compat aliases
    # ==================================================================

    def wire_gate(
        self,
        source_idx: int,
        output_gate: str,
        target_idx: int,
        input_gate: str,
        *,
        name: str = "",
        start_point: tuple[float, float] = (0.0, 0.0),
        end_point: tuple[float, float] = (0.0, 0.0),
    ) -> int:
        """[Deprecated] Alias for ``connect()``. Returns wire_id when runtime
        is active, else 0.

        Prefer ``connect()`` — it works in both modes and returns the
        constraint dict.
        """
        self.connect(
            source_idx, output_gate, target_idx, input_gate,
            name=name, start_point=start_point, end_point=end_point,
        )
        if self._runtime_active and self._world is not None:
            wires = self._world.gate_wires.list_all()
            # Return last wire id (most recently added)
            return wires[-1].wire_id if wires else 0
        return 0

    def unwire_gate(
        self,
        wire_id: int | None = None,
        *,
        source_idx: int | None = None,
        target_idx: int | None = None,
        output_gate: str | None = None,
        input_gate: str | None = None,
    ) -> int:
        """[Deprecated] Alias for ``disconnect()``."""
        if wire_id is not None:
            return self.disconnect(source_idx=0, wire_id=wire_id)
        return self.disconnect(
            source_idx or 0,
            output_gate=output_gate,
            target_idx=target_idx,
            input_gate=input_gate,
        )

    def wires(self) -> list[dict]:
        """[Deprecated] List gate wires from the live registry or document."""
        if self._runtime_active and self._world is not None:
            out = []
            for w in self._world.gate_wires.list_all():
                out.append({
                    "wire_id": w.wire_id,
                    "source_idx": w.source_idx,
                    "target_idx": w.target_idx,
                    "output_gate": w.output_gate,
                    "input_gate": w.input_gate,
                    "name": w.name,
                })
            return out
        return self.list_connections()

    # ==================================================================
    # Internal helpers
    # ==================================================================

    def _raw_containers(self) -> list[dict]:
        """Return the mutable saveObjectContainers list (creates if missing)."""
        return self._doc.raw_data.setdefault("saveObjectContainers", [])

    def _require_runtime(self) -> None:
        if not self._runtime_active or self._world is None or self._runner is None:
            raise RuntimeError(
                "Runtime not active; call .load() or use 'with MelsaveSession(...) as s:'"
            )
