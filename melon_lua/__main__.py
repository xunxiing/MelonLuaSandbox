"""CLI entry: `python -m melon_lua script.lua [options]`."""
import argparse
import json
import sys
import time
from pathlib import Path

from . import MelonScriptRunner, WorldContext


def _print_log(level: str, msg: str):
    tag = {"print": "", "warn": "[warn] ", "error": "[error] ",
           "info": "[info] "}.get(level, "")
    print(f"{tag}{msg}")


def _format_outputs(outputs: dict) -> str:
    if not outputs:
        return "(no outputs)"
    parts = []
    for cat, items in outputs.items():
        if not items:
            continue
        for k, v in items.items():
            if v is None or v == "" or v == 0:
                continue
            parts.append(f"{cat}.{k} = {_fmt(v)}")
    return "\n  ".join(parts) if parts else "(no non-default outputs)"


def _fmt(v):
    if isinstance(v, dict):
        return json.dumps(v, default=str)
    if isinstance(v, list):
        return json.dumps(v, default=str)
    return repr(v)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="melon-lua",
        description="Run a melon Lua chip in a sandbox.",
    )
    p.add_argument("script", nargs="?", help="path to .lua chip script")
    p.add_argument("--stdin", action="store_true", help="read script from stdin")
    p.add_argument("--duration", type=float, default=5.0,
                   help="run for N seconds (default 5). Ignored if --ticks is set.")
    p.add_argument("--ticks", type=int, default=None,
                   help="run exactly N ticks (overrides --duration)")
    p.add_argument("--tps", type=float, default=20.0,
                   help="ticks per second (default 20)")
    p.add_argument("--max-instructions", type=int, default=100000)
    p.add_argument("--quiet", action="store_true",
                   help="suppress real-time logs; print summary at end")
    p.add_argument("--log-file", help="write full log to this file")
    p.add_argument("--inputs", help="JSON file with static inputs dictionary")
    p.add_argument("--inputs-timeline", help="JSON {tick:{...inputs...}, ...} — sets inputs at given ticks")
    p.add_argument("--seed-entity", action="append", default=[],
                   help="seed entity: NAME[,x,y]. Dynamic (affected by physics).")
    p.add_argument("--seed-static", action="append", default=[],
                   help="seed static entity: NAME[,x,y]. Immovable (floor/walls).")
    p.add_argument("--api-list", action="store_true",
                   help="print the API surface and exit")
    args = p.parse_args(argv)

    if args.api_list:
        _print_api_list()
        return 0

    if args.stdin:
        source = sys.stdin.read()
        chunk_name = "@stdin"
    elif args.script:
        source = Path(args.script).read_text(encoding="utf-8")
        chunk_name = f"@{Path(args.script).name}"
    else:
        p.error("provide a script or --stdin")
        return 2

    world = WorldContext()

    # Seed entities
    for spec in args.seed_entity:
        parts = spec.split(",")
        name = parts[0]
        x = float(parts[1]) if len(parts) > 1 else 0.0
        y = float(parts[2]) if len(parts) > 2 else 0.0
        world.spawn_entity(name=name, x=x, y=y, dynamic=True)

    for spec in args.seed_static:
        parts = spec.split(",")
        name = parts[0]
        x = float(parts[1]) if len(parts) > 1 else 0.0
        y = float(parts[2]) if len(parts) > 2 else 0.0
        world.spawn_entity(name=name, x=x, y=y, dynamic=False)

    inputs = None
    if args.inputs:
        inputs = json.loads(Path(args.inputs).read_text(encoding="utf-8"))

    # Build inputs_provider based on chosen strategy
    inputs_provider = None
    if args.inputs_timeline:
        timeline = json.loads(Path(args.inputs_timeline).read_text(encoding="utf-8"))
        timeline_int = {int(k): v for k, v in timeline.items()}
        last_inputs = [None]  # mutable closure cell
        def timeline_provider(i):
            if (i + 1) in timeline_int:  # i is 0-based; user uses tick numbers
                last_inputs[0] = timeline_int[i + 1]
                print(f"[inputs-timeline] tick {i+1}: {last_inputs[0]}")
            return last_inputs[0]
        inputs_provider = timeline_provider
        print(f"[inputs] timeline with {len(timeline_int)} change points")
    elif inputs is not None:
        inputs_provider = lambda i: inputs

    runner = MelonScriptRunner(
        tps=args.tps,
        max_instructions=args.max_instructions,
        world=world,
        quiet=args.quiet,
        log_callback=None if args.quiet else _print_log,
    )

    if not runner.compile(source, chunk_name=chunk_name):
        print(f"[compile error] {runner.last_error}", file=sys.stderr)
        return 1

    print(f"[chip] compiled. OnInit={runner.has_on_init} "
          f"OnTick={runner.has_on_tick} "
          f"OnActivated={runner._has_on_activated}")

    # Determine tick count
    if args.ticks is not None:
        total_ticks = args.ticks
        print(f"[run] {total_ticks} ticks @ {args.tps} TPS")
    else:
        total_ticks = int(args.duration * args.tps)
        print(f"[run] {args.duration}s × {args.tps} TPS = {total_ticks} ticks")

    def on_tick(i, dt, result):
        if result.get("error"):
            return
        if i == total_ticks - 1:
            print(f"\n[final outputs]\n  {_format_outputs(result['outputs'])}")

    runner.run_loop(
        ticks=args.ticks,
        duration=args.duration if args.ticks is None else None,
        tick_callback=on_tick,
        inputs_provider=inputs_provider,
    )

    if runner.last_error:
        print(f"\n[last error] {runner.last_error}", file=sys.stderr)

    # Logs
    if args.quiet:
        logs = runner.logs
        print(f"\n[log summary] {len(logs)} entries")
        for level, msg in logs[:20]:
            print(f"  {level}: {msg}")
        if len(logs) > 20:
            print(f"  ... (+{len(logs)-20} more)")

    if args.log_file:
        Path(args.log_file).write_text(
            f"# Melon Lua Sandbox log\n"
            f"# Script: {chunk_name}\n"
            f"# Duration: {args.duration}s @ {args.tps} TPS\n\n"
            + "\n".join(f"[{lvl}] {msg}" for lvl, msg in runner.logs),
            encoding="utf-8",
        )
        print(f"\n[log file] {args.log_file}")

    return 0


def _print_api_list():
    print("""\
Melon Lua API surface (from Example_ApiReference_en.lua):

LIFECYCLE:
  OnInit()  OnTick()  OnSpawned(reqId, entities)  OnActivated()
  OnDeactivated()  OnDestroy()

GLOBALS:
  print(...)  warn(...)  error_log(...)
  Entity(id) → table with metatable; Entity(0/nil) → _noop
  inputs.<cat>.<key>      categories: num int string vec color entity
                                  array_num array_string array_vec array_entity
  outputs.<cat>.<key>     (write every tick)
  shared.<key>            cross-chip table
  signal.on(ch,cb)/off/emit/defer
  register_module(name,table)  require(name)

MODULES:
  entity.*     getPosition/setPosition/getAngle/setAngle/getScale/setScale
               getNormal/localToWorld/worldToLocal/localAngleToWorld/worldAngleToLocal
               getVelocity/setVelocity/getAngularVelocity/setAngularVelocity
               addForce/addTorque/addForceAtPosition/getVelocityAtPoint
               getMass/getCenterOfMass/getGravityScale/setGravityScale
               freeze/freezeRotation/setCollisionEnabled
               getTemperature/setTemperature/isOnFire/isFrozen/ignite/extinguish
               getHealth/isBreakable
               getColor/setColor/getName/getLocalizedName/isVisible/setVisible
               getVoltage
               isDraggable/setDraggable/activate/getActivationInput/delete
               getId/isValid/all/find
               getRoot/getParent/getChildren
               getSize/getBaseSize/getBounds/getFullBounds/getColliderBounds
               lookAt/getElevation/canBeActivated/getPhysicMaterial
               subscribeCollision*/unsubscribeCollision*
               subscribeTrigger*/unsubscribeTrigger*
               subscribeWireConnected/Disconnected + unsubscribe
               unsubscribeAll
  env.*        time deltaTime fixedDeltaTime timeScale setTimeScale frameCount
               sessionTime entityCount isWorld isWorldEditor systemTime systemDate
               toDate toTimeFormat parseDate
  camera.*     getPosition setPosition getZoom setZoom follow unfollow isFollowing
  input.*      pointerDown/Up/Pos/ScreenPos/Delta/Raycast/RaycastAll/isOverUI
               pointerDownFiltered/UpFiltered touchCount touchSet/Down/Up/Age/Id
               touchPos/ScreenPos/StartScreenPos/Delta/SwipeDelta/Tap/TapCount/Swipe
               touchIsOverUI/StartedOverUI pinchDistance/Angle/Center key keyDown
  spawn.*      getItems/ItemsString/ItemCount getSaves/SavesString/SaveCount
               getResourceSaves*/ModCount/Mods create createWithAngle clone
               cloneTemp createSave createMod destroy getNameByAlias existsByAlias
  chip.*       has getType getInputs getOutputs getValue setValue hasWire
               getActivation setActivation getName getTPS
  mechanic.*   has getType getInputs getOutputs getValue setValue hasWire
               getActivation setActivation
  uicontrol.*  hasUIControl getElements findElement getElementsByType
               getInputGates getOutputGates getValue setValue hasWire
               getAnchors getAnchoredPosition setAnchoredPosition
  world.*      isSessionActive startSession endSession save load reset
               clearCorpses clearDecals clearGibs clearLiving radioSignal
  variables.*  Set(key,val)→1/0  Get(key)→val

STANDARD LIBRARY (allowed):
  math string table coroutine pairs ipairs type tostring tonumber
  select unpack pcall setmetatable getmetatable error next rawequal
""")


if __name__ == "__main__":
    sys.exit(main())
