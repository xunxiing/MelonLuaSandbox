"""print / warn / error_log — backed by PrintApiModule.

Real game: LuaConsoleBuffer + logOwner. Each call writes to console AND
CustomDebug log. Here we just append to world.console_buffer.

Lua contract (from ApiReference):
    print(...)        -- args joined by tab
    warn(...)         -- same
    error_log(...)    -- same

lupa registers Python callables via g["print"] = fn. We need to accept
varargs and join them tab-separated like Lua's stock print.
"""
from typing import Any, Callable, Optional


def _to_str(v: Any) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    # lupa exposes Lua tables as _LuaTable wrappers with .values() etc.
    if hasattr(v, "keys"):
        try:
            d = {k: v[k] for k in v.keys()}
            return str(d)
        except Exception:
            pass
    return s


def register_print_backend(
    lua, g, world,
    on_log: Optional[Callable[[str, str], None]] = None,
    error_log_fn: Optional[Callable[[str], None]] = None,
):
    def _print(*args) -> int:
        msg = "\t".join(_to_str(a) for a in args)
        world.console_buffer.append(("print", msg))
        if on_log:
            on_log("print", msg)
        return 0

    def _warn(*args) -> int:
        msg = "\t".join(_to_str(a) for a in args)
        world.console_buffer.append(("warn", msg))
        if on_log:
            on_log("warn", msg)
        return 0

    def _error_log(*args) -> int:
        msg = "\t".join(_to_str(a) for a in args)
        world.console_buffer.append(("error", msg))
        if on_log:
            on_log("error", msg)
        elif error_log_fn:
            error_log_fn(msg)
        return 0

    g["print"] = _print
    g["warn"] = _warn
    g["error_log"] = _error_log
