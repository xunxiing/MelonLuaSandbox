"""Exercise the marquee chip: default scroll, loop, and custom override."""
from melon_lua import MelsaveSession

DEFAULT = "欢迎乘坐甜瓜铁路运输集团云水号动车组      G3611   甜瓜东→万城岛松山，本站：甜瓜东  下一站：雨林港"
VISIBLE = 18
STEP = 4
TICKS = 400

def chars_of(s: str) -> list[tuple[str, int]]:
    out = []
    data = s.encode("utf-8")
    i = 0
    while i < len(data):
        b = data[i]
        if b < 128:
            ln = 1
        elif b < 224:
            ln = 2
        elif b < 240:
            ln = 3
        else:
            ln = 4
        ch = data[i : i + ln].decode("utf-8")
        out.append((ch, 1 if b < 128 else 2))
        i += ln
    return out

def width_of(s: str) -> int:
    return sum(w for _, w in chars_of(s))

def char_ends(s: str) -> list[int]:
    seen = 0
    ends = []
    for _, w in chars_of(s):
        seen += w
        ends.append(seen)
    return ends

def slice_by_width(s: str, start_w: int, take_w: int) -> str:
    out = []
    seen = 0
    for ch, w in chars_of(s):
        start_at = seen
        seen += w
        if seen <= start_w:
            continue
        if start_at + w > start_w + take_w:
            break
        if start_at >= start_w:
            out.append(ch)
    return "".join(out)

def expect_at(tick: int, base: str) -> str:
    scroll = base + "        "
    ends = char_ends(scroll)
    offset = 0
    for _ in range(tick // STEP):
        idx = 0
        for i, end in enumerate(ends):
            if end > offset:
                idx = i
                break
        offset = 0 if idx >= len(ends) - 1 else ends[idx]
    return slice_by_width(scroll + scroll, offset, VISIBLE)

def main() -> None:
    fails = []
    with MelsaveSession("marquee_screen.melsave") as s:
        r = s.debug_run(ticks=TICKS)
        if r.get("error"):
            fails.append(f"default run error: {r['error']}")
        frames = r.get("frames") or []
        if len(frames) != TICKS:
            fails.append(f"expected {TICKS} frames, got {len(frames)}")
        windows = []
        for i, fr in enumerate(frames):
            if fr.get("error"):
                fails.append(f"tick {i} error: {fr['error']}")
                break
            got = ((fr.get("outputs") or {}).get("string") or {}).get("text", "")
            windows.append(got)
            want = expect_at(i + 1, DEFAULT)
            if got != want and len(fails) < 3:
                fails.append(f"tick {i + 1}: got {got!r} want {want!r}")
            if width_of(got) > VISIBLE and len(fails) < 4:
                fails.append(f"tick {i + 1} wider than {VISIBLE}: {got!r} ({width_of(got)})")
        uniq = []
        for w in windows:
            if not uniq or uniq[-1] != w:
                uniq.append(w)
        if len(uniq) < 8:
            fails.append(f"scroll barely moved: {len(uniq)} unique windows")
        if windows and windows[0] == windows[-1]:
            fails.append("window did not advance across the run")
        looped = any(w == windows[0] for w in windows[STEP * 4 :]) if windows else False
        if windows and not looped:
            fails.append("did not loop back to the first window")
        print("first", windows[0] if windows else None)
        print("mid  ", windows[len(windows) // 2] if windows else None)
        print("last ", windows[-1] if windows else None)
        print("unique", len(uniq), "looped", looped)

        custom = "测试滚动ABC"
        r2 = s.debug_run(ticks=8, inputs={"string": {"text": custom}})
        if r2.get("error"):
            fails.append(f"custom run error: {r2['error']}")
        f2 = r2.get("frames") or []
        if f2:
            got = ((f2[0].get("outputs") or {}).get("string") or {}).get("text", "")
            want = expect_at(1, custom)
            print("custom", got)
            if got != want:
                fails.append(f"custom override: got {got!r} want {want!r}")
            if "欢迎乘坐" in got:
                fails.append("custom input did not override default text")

    if fails:
        print("FAIL")
        for line in fails:
            print(" -", line)
        raise SystemExit(1)
    print("PASS")

if __name__ == "__main__":
    main()
