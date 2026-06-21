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


class MelsaveSession:
    """One session = one save file + one world + one chip runner.

    Lifecycle: created -> load() -> [run_chip / create_rope / snapshot]* ->
    save_as() -> close().
    """

    def __init__(
        self,
        melsave_path: str | Path,
        *,
        tps: float = 20.0,
        quiet: bool = True,
    ):
        self.melsave_path = Path(melsave_path)
        self.tps = float(tps)
        self._quiet = bool(quiet)
        self._doc: Optional[MelsaveDocument] = None
        self._world: Optional[WorldContext] = None
        self._runner: Optional[MelonScriptRunner] = None
        self._loaded = False

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
        self._loaded = True
        return self

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

    def run_chip(
        self,
        source: str,
        *,
        ticks: int = 1,
        inputs: Optional[dict] = None,
        chunk_name: str = "@session_chip.lua",
    ) -> dict:
        """Compile a Lua chip and run it for `ticks` ticks. Returns last tick result.

        If ticks == 0, only compiles + calls OnInit (no OnTick). If ticks >= 1,
        OnInit is called first, then OnTick runs `ticks` times.
        """
        self._require_loaded()
        r = self._runner
        assert r is not None
        if not r.compile(source, chunk_name=chunk_name):
            return {"error": r.last_error or "compile failed", "outputs": {}}
        r.call_on_init()
        if ticks <= 0:
            return {"error": None, "outputs": r.get_outputs()}
        if ticks == 1:
            return r.run_tick(inputs=inputs)
        provider = (lambda i: inputs) if inputs is not None else None
        r.run_loop(ticks=ticks, inputs_provider=provider)
        return {"error": r.last_error, "outputs": r.get_outputs()}

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
        """Diff the live world against the original save and write a new .melsave."""
        self._require_loaded()
        assert self._world is not None
        assert self._doc is not None
        return write_world_to_melsave(
            self._world,
            self._doc,
            out_path,
            write_icon=write_icon,
        )

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
