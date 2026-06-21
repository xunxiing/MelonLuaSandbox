(function () {
  var needles = [
    "entityCount",
    "EntityCount",
    "frameCount",
    "RegisterEnvStackGlobals",
    "entity.all",
    "GetInstanceID",
    "libil2cpp",
  ];
  var ranges = Process.enumerateRanges({ protection: "r--", coalesce: true });

  function scan(needle) {
    var pat = needle
      .split("")
      .map(function (c) {
        var h = c.charCodeAt(0).toString(16);
        return h.length === 1 ? "0" + h : h;
      })
      .join(" ");
    var n = 0;
    var addr = null;
    for (var i = 0; i < ranges.length; i++) {
      var r = ranges[i];
      if (r.size < 4096 || r.size > 100 * 1024 * 1024) continue;
      try {
        var ms = Memory.scanSync(r.base, r.size, pat);
        if (ms.length) {
          n += ms.length;
          if (!addr) addr = ms[0].address;
        }
      } catch (e) {}
    }
    return { needle: needle, count: n, addr: addr ? addr.toString() : null };
  }

  send({ type: "scan", out: needles.map(scan) });

  var exec = Process.enumerateRanges({ protection: "r-x", coalesce: true });
  var large = exec.filter(function (r) {
    return r.size > 30 * 1024 * 1024;
  });
  send({
    type: "large_exec",
    count: large.length,
    samples: large.slice(0, 8).map(function (r) {
      return {
        base: r.base.toString(),
        size: r.size,
        file: r.file ? r.file.path : null,
      };
    }),
  });

  var mods = Process.enumerateModules().filter(function (m) {
    return m.size > 20 * 1024 * 1024;
  });
  send({
    type: "large_modules",
    mods: mods.map(function (m) {
      return { name: m.name, base: m.base.toString(), size: m.size, path: m.path };
    }),
  });
})();