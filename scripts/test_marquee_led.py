"""Check the LED marquee actually scrolls and stays on the 64x16 matrix."""
from melon_lua import MelsaveSession

W, H = 64, 16

def sig(buf):
    cols = []
    for x in range(W):
        n = 0
        for y in range(H):
            p = buf[y * W + x]
            if isinstance(p, dict) and p.get("y", 0) > 0.5:
                n += 1
        cols.append(n)
    return tuple(cols)

def main():
    fails = []
    with MelsaveSession("marquee_led.melsave") as s:
        r = s.debug_run(ticks=12)
        if r.get("error"):
            fails.append(str(r["error"]))
        frames = r.get("frames") or []
        sigs = []
        for i, fr in enumerate(frames):
            buf = ((fr.get("outputs") or {}).get("array_vec") or {})
            key = next(iter(buf), None)
            pixels = buf.get(key) if key else None
            if not pixels or len(pixels) != W * H:
                fails.append(f"tick {i + 1} buffer {0 if not pixels else len(pixels)}")
                continue
            sigs.append(sig(pixels))
            lit = sum(1 for n in sigs[-1] if n)
            print(f"t{i + 1:02d} lit_cols={lit} head={sigs[-1][:8]}")
        # Chip steps on even ticks: frame 1 holds, then each pair shares a shift.
        if len(sigs) >= 6 and sigs[1] == sigs[2] and sigs[3] == sigs[4] and sigs[1] != sigs[3]:
            print("scroll step ok")
        else:
            fails.append("scroll did not advance on even ticks")
        if len(set(sigs)) < 3:
            fails.append("not enough unique frames")
    if fails:
        print("FAIL")
        for line in fails:
            print(" -", line)
        raise SystemExit(1)
    print("PASS")

if __name__ == "__main__":
    main()
