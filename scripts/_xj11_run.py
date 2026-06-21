"""Test xj11 VP chips in sandbox runner."""
from melon_lua import MelsaveSession
import os

path = os.path.join('temp', 'xj11', 'xj 11(1).melsave')
with MelsaveSession(path) as s:
    print('loaded:', len(s.world.entities), 'entities')
    for lid, ent in s.world.entities.items():
        print('  lid={} oid={} pos=({:.2f},{:.2f})'.format(lid, ent.object_id, ent.position_x, ent.position_y))

    # Try running each compiled VP chip
    for idx in [4, 7, 8, 9, 11, 12]:
        chip_path = 'temp/xj11_idx{}.lua'.format(idx)
        if not os.path.exists(chip_path):
            continue
        with open(chip_path, 'r', encoding='utf-8') as f:
            chip_src = f.read()

        print('--- running idx{} chip for 10 ticks ---'.format(idx))
        try:
            s.run_chip(chip_src, ticks=10)
            snap = s.snapshot()
            print('  OK, snapshot keys:', list(snap.keys())[:5])
        except Exception as e:
            print('  ERROR: {}: {}'.format(type(e).__name__, e))
