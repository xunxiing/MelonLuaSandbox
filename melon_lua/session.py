"""High-level session: bind a .melsave file to a sandbox lifecycle.

A `MelsaveSession` owns the full pipeline: read the save, spawn its objects
into a WorldContext, compile/run Lua chips against that world, create/remove
ropes, snapshot state, and write the modified scene back to a new .melsave.

Typical agent workflow::

    from melon_lua import MelsaveSession

    session = MelsaveSession("input.melsave")
    session.load()
    session.run_chip(chip_source, ticks=100)
    session.create_rope(from_id=1, to_id=2, kind="Simple")
    snap = session.snapshot()
    session.save_as("output.melsave")
    session.close()

The original `MelsaveDocument` is held internally so `save_as` can diff the
live world against it without the caller managing references.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .melsave import MelsaveDocument, read_melsave, spawn_document_into_world
from .melsave_writer import write_world_to_melsave, build_diff_from_world
from .world import WorldContext
from .runner import MelonScriptRunner

# Packaged empty world template — minimal valid save with zero objects.
_EMPTY_TEMPLATE = Path(__file__).parent / "data" / "empty.melsave"


class MelsaveSession:
    """One session = one save file + one world + one chip runner.

    Lifecycle: created -> load() -> [run_chip / create_rope / snapshot]* ->
    save_as() -> close().
    """

    def __init__(
        self,
        melsave_path: str | Path | None = None,
        *,
        tps: float = 20.0,
        quiet: bool = True,
    ):
        if melsave_path is None:
            # Bare constructor -> load the packaged empty world template so
            # the "create session then operate" intuitive path works.
            melsave_path = _EMPTY_TEMPLATE
        self.melsave_path = Path(melsave_path)
        self.tps = float(tps)
        self._quiet = bool(quiet)
        self._doc: Optional[MelsaveDocument] = None
        self._world: Optional[WorldContext] = None
        self._runner: Optional[MelonScriptRunner] = None
        self._loaded = False
        # Chips added in-session that should persist on save_as(). Each entry
        # is a raw saveObjects dict (Lua chip container). They are appended to
        # the patched saveObjectContainers on write-back.
        self._pending_chips: list[dict] = []
        # Track which chip container (by index into _pending_chips) the last
        # run_chip() compiled, so the source can be synced before save.
        self._active_chip_idx: Optional[int] = None

    @classmethod
    def create_empty(cls, **kw: Any) -> "MelsaveSession":
        """Create a session backed by an empty world.

        Equivalent to ``MelsaveSession()`` (which now defaults to the packaged
        empty template), but makes intent explicit at call sites.
        """
        return cls(None, **kw)

    # ===== Lifecycle =====

    def load(self) -> "MelsaveSession":
        """Read the melsave, spawn all objects into a fresh world, build runner."""
        if self._loaded:
            return self
        self._doc = read_melsave(self.melsave_path)
        self._world = WorldContext()
        spawn_document_into_world(self._doc, self._world)
        self._runner = MelonScriptRunner(
            tps=self.tps,
            world=self._world,
            quiet=self._quiet,
        )
        # Load existing mechanic gate wires from the save's raw constraints
        self._load_gate_wires_from_doc()
        self._loaded = True
        return self

    def _load_gate_wires_from_doc(self) -> None:
        """Populate ``world.gate_wires`` from the document's raw constraints."""
        assert self._world is not None
        assert self._doc is not None
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
        self._doc = None
        self._loaded = False

    def __enter__(self) -> "MelsaveSession":
        return self.load()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ===== Chip execution =====

    def add_lua_chip(
        self,
        source: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        inputs: list[dict] | None = None,
        outputs: list[dict] | None = None,
        variables: list[dict] | None = None,
        tps: int = 30,
        priority: int = 0,
        title: str = "",
    ) -> int:
        """Add a Lua chip container to the session (persisted on save_as).

        Creates a saveObjects entry for a Lua chip (objectId=507707712) with
        the given source and gates, and tracks it so ``save_as()`` includes it
        in the exported melsave. Also marks it as the active chip so subsequent
        ``run_chip()`` calls (without ``container_idx``) will sync source changes.

        Returns the index of the chip in ``self._pending_chips`` (also the
        container index it will occupy after existing containers).
        """
        self._require_loaded()
        assert self._doc is not None
        from .melsave_builder import _build_chip_save_objects
        base = len(self._doc.objects)
        so = _build_chip_save_objects(
            source, x, y,
            inputs=inputs, outputs=outputs, variables=variables,
            tps=tps, priority=priority, title=title,
        )
        self._pending_chips.append(so)
        self._active_chip_idx = len(self._pending_chips) - 1
        return self._active_chip_idx

    def run_chip(
        self,
        source: str,
        *,
        ticks: int = 1,
        inputs: Optional[dict] = None,
        chunk_name: str = "@session_chip.lua",
        container_idx: Optional[int] = None,
    ) -> dict:
        """Compile a Lua chip and run it for `ticks` ticks. Returns last tick result.

        If ticks == 0, only compiles + calls OnInit (no OnTick). If ticks >= 1,
        OnInit is called first, then OnTick runs `ticks` times.

        Args:
            container_idx: If given, sync the source back into that pending
                chip container so it persists on save_as(). Chips created via
                add_lua_chip() auto-sync; pass the index returned by it to
                keep edits live.
        """
        self._require_loaded()
        r = self._runner
        assert r is not None
        if not r.compile(source, chunk_name=chunk_name):
            return {"error": r.last_error or "compile failed", "outputs": {}}
        # Sync source into pending chip container for persistence
        idx = container_idx if container_idx is not None else self._active_chip_idx
        if idx is not None and 0 <= idx < len(self._pending_chips):
            self._sync_chip_source(idx, source)
        r.call_on_init()
        if ticks <= 0:
            return {"error": None, "outputs": r.get_outputs()}
        if ticks == 1:
            return r.run_tick(inputs=inputs)
        provider = (lambda i: inputs) if inputs is not None else None
        r.run_loop(ticks=ticks, inputs_provider=provider)
        return {"error": r.last_error, "outputs": r.get_outputs()}

    def _sync_chip_source(self, idx: int, source: str) -> None:
        """Update the lua_chip_source metadata of a pending chip container."""
        so = self._pending_chips[idx]
        for sm in so.get("saveMetaDatas", []):
            if sm.get("key") == "lua_chip_source":
                sm["stringValue"] = source
                return

    def compile_only(self, source: str, chunk_name: str = "@session_chip.lua") -> bool:
        """Compile a chip without running. Returns True on success."""
        self._require_loaded()
        assert self._runner is not None
        return self._runner.compile(source, chunk_name=chunk_name)

    def tick(self, inputs: Optional[dict] = None) -> dict:
        """Run a single OnTick on the already-compiled chip."""
        self._require_loaded()
        assert self._runner is not None
        return self._runner.run_tick(inputs=inputs)

    # ===== Entity / world access =====

    @property
    def world(self) -> WorldContext:
        self._require_loaded()
        assert self._world is not None
        return self._world

    @property
    def runner(self) -> MelonScriptRunner:
        self._require_loaded()
        assert self._runner is not None
        return self._runner

    @property
    def document(self) -> MelsaveDocument:
        self._require_loaded()
        assert self._doc is not None
        return self._doc

    def entities(self) -> list[dict]:
        """Snapshot list of alive entities: {entity_id, local_id, object_id, name, x, y, angle}."""
        self._require_loaded()
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
        return self._world.get_entity(entity_id) if self._world else None

    def spawn(self, name_or_id, x: float = 0.0, y: float = 0.0, **kw):
        """Spawn a new entity into the world. Returns the Entity."""
        self._require_loaded()
        assert self._world is not None
        return self._world.spawn_entity(name_or_id, x, y, **kw)

    def remove(self, entity_id: int) -> bool:
        """Remove an entity. Returns True if it existed."""
        self._require_loaded()
        assert self._world is not None
        e = self._world.entities.get(entity_id)
        if e is None:
            return False
        self._world.remove_entity(entity_id)
        return True

    # ===== Ropes / constraints =====

    def create_rope(
        self,
        from_id: int,
        to_id: int,
        kind: str | int = "Simple",
        **params,
    ) -> int:
        """Create a rope/constraint between two entities. Returns constraint_id."""
        self._require_loaded()
        assert self._world is not None
        return self._world.create_rope(from_id, to_id, kind, **params)

    def remove_rope(self, constraint_id: int) -> bool:
        """Alias for destroy_rope. Removes a rope and its Box2D joint."""
        self._require_loaded()
        assert self._world is not None
        return self._world.destroy_rope(constraint_id)

    def set_rope_param(self, constraint_id: int, key: str, value) -> bool:
        self._require_loaded()
        assert self._world is not None
        return self._world.set_rope_param(constraint_id, key, value)

    def ropes(self) -> list[dict]:
        """List all constraints in the registry."""
        self._require_loaded()
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

    # ===== Mechanic gate wires (signal connections) =====

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
        """Hot-wire a mechanic gate connection between two containers.

        Adds a signal wire from ``output_gate`` on container ``source_idx``
        to ``input_gate`` on container ``target_idx``. The wire lives in the
        session's ``GateWireRegistry`` and is serialized on ``save_as()``.

        Args:
            source_idx: Container index of the source (output) object.
            output_gate: Output gate name on the source object.
            target_idx: Container index of the target (input) object.
            input_gate: Input gate name on the target object.
            name: Optional display name for the wire.
            start_point: Visual offset of the source port (local space).
            end_point: Visual offset of the target port (local space).

        Returns:
            The wire_id (auto-incremented).
        """
        self._require_loaded()
        assert self._world is not None
        return self._world.gate_wires.connect(
            source_idx, output_gate, target_idx, input_gate,
            name=name, start_point=start_point, end_point=end_point,
        )

    def unwire_gate(
        self,
        wire_id: int | None = None,
        *,
        source_idx: int | None = None,
        target_idx: int | None = None,
        output_gate: str | None = None,
        input_gate: str | None = None,
    ) -> int:
        """Hot-disconnect gate wire(s).

        If ``wire_id`` is given, removes that specific wire.
        Otherwise removes all wires matching the filter combination.
        Returns the number of wires removed.
        """
        self._require_loaded()
        assert self._world is not None
        if wire_id is not None:
            return 1 if self._world.gate_wires.disconnect(wire_id) else 0
        return self._world.gate_wires.disconnect_matching(
            source_idx=source_idx,
            target_idx=target_idx,
            output_gate=output_gate,
            input_gate=input_gate,
        )

    def wires(self) -> list[dict]:
        """List all gate wires in the registry."""
        self._require_loaded()
        assert self._world is not None
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

    # ===== Snapshot / diff =====

    def snapshot(self) -> dict:
        """Return a serializable snapshot of the current world state."""
        self._require_loaded()
        assert self._world is not None
        w = self._world
        return {
            "tick": w.current_tick,
            "elapsed": w.elapsed_time,
            "entities": self.entities(),
            "ropes": self.ropes(),
            "variables": dict(w.chip_variables),
            "entity_count": sum(1 for e in w.entities.values() if getattr(e, "alive", True)),
        }

    def diff(self) -> dict:
        """Return the WorldDiff as a plain dict (for inspection/logging)."""
        self._require_loaded()
        assert self._world is not None
        assert self._doc is not None
        d = build_diff_from_world(self._world, self._doc)
        return {
            "modified": {str(k): v for k, v in d.modified_objects.items()},
            "added_count": len(d.added_objects),
            "removed": sorted(d.removed_local_ids),
            "constraint_lids": sorted(d.modified_constraints.keys()),
        }

    # ===== Write back =====

    def save_as(
        self,
        out_path: str | Path,
        *,
        write_icon: bool = True,
    ) -> Path:
        """Diff the live world against the original save and write a new .melsave.

        Lua chips added via ``add_lua_chip()`` are appended as new containers.
        Source edits from ``run_chip()`` are synced back into the chip's
        ``lua_chip_source`` metadata so the exported save is runnable on the
        real device.

        Returns the resolved absolute path of the written file.
        """
        self._require_loaded()
        assert self._world is not None
        assert self._doc is not None
        p = write_world_to_melsave(
            self._world,
            self._doc,
            out_path,
            write_icon=write_icon,
            extra_containers=list(self._pending_chips) if self._pending_chips else None,
        )
        return Path(p).resolve()

    # ===== Logs / errors =====

    @property
    def logs(self) -> list:
        self._require_loaded()
        assert self._runner is not None
        return self._runner.logs

    @property
    def last_error(self) -> Optional[str]:
        return self._runner.last_error if self._runner else None

    @property
    def outputs(self) -> dict:
        self._require_loaded()
        assert self._runner is not None
        return self._runner.get_outputs()

    # ===== Internal =====

    def _require_loaded(self) -> None:
        if not self._loaded or self._world is None or self._runner is None or self._doc is None:
            raise RuntimeError("MelsaveSession not loaded; call .load() or use as context manager")
