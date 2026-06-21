"""Test converted Lua chip melsave: load, run each chip, verify."""
import json
import zipfile

from melon_lua import MelsaveSession


def test_converted_melsave(path):
    # Extract lua sources from melsave
    with zipfile.ZipFile(path, 'r') as zf:
        data = json.loads(zf.read('Data'))

    lua_sources = []
    for i, cont in enumerate(data.get('saveObjectContainers', [])):
        so = cont.get('saveObjects', {})
        sm = so.get('saveMetaDatas', [])
        for m in sm:
            if m.get('key') == 'lua_chip_source':
                lua_sources.append((i, m['stringValue']))
                break

    print('Found {} Lua chips in {}'.format(len(lua_sources), path))

    # Load melsave into sandbox
    with MelsaveSession(path) as s:
        print('Loaded {} entities'.format(len(s.world.entities)))
        for idx, src in lua_sources:
            lines = src.count('\n') + 1
            print('--- chip[{}] {} lines ---'.format(idx, lines))
            try:
                s.run_chip(src, ticks=5)
                snap = s.snapshot()
                print('  OK, tick={}'.format(snap.get('tick', '?')))
            except Exception as e:
                print('  ERROR: {}: {}'.format(type(e).__name__, e))


if __name__ == '__main__':
    test_converted_melsave('temp/xj11_lua.melsave')
