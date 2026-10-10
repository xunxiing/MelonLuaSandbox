-- 路况颠簸检测芯片 v3
-- 两个激光雷达(Range Finder)扫描前方路面。
-- 核心：按世界前向坐标 u 分桶(0.25/桶)，滑动窗口[车前1, 车+8]，
-- 桶随车推进进出窗，增量维护线性回归和(无全量重算)。
-- 残差 RMS = 颠簸度 score；坑深 = 最大残差；roll = 左右高度差 RMS。
-- 上坡：滑窗线性回归去趋势，slope=坡度；R2<0.7(数据被坑遮挡/混杂)时冻结 slope。
-- 输入: body/ranger1/ranger2(entity) r1dist/r2dist(number) maxage(number,可选)
-- 输出: score slope pothole roll status
-- 挂载建议：雷达朝前下 20°，平路落点应在车前 4~8 单位内(太高会看不见平路)。

local BIN = 0.25          -- 桶宽(单位长度)
local NEAR = 1.0          -- 窗口近端(车前1)
local FAR = 8.0           -- 窗口远端(车前8)
local MIN_N = 3           -- 每侧最少桶数(置信)
local UPDATE_EVERY = 36   -- 输出节流(每36 tick = 180tps下0.2秒)

local bufL, bufR = {}, {}     -- 桶号 -> 路面高度
local ageL, ageR = {}, {}     -- 桶号 -> 最后更新 tick
local sumL = {0, 0, 0, 0, 0, 0}  -- n, Su, Sh, Suu, Suh, Shh (左)
local sumR = {0, 0, 0, 0, 0, 0}
local ntick = 0
local last_slope = 0.0

local function bin_add(sums, u, h, sign)
  sums[1] = sums[1] + sign
  sums[2] = sums[2] + sign * u
  sums[3] = sums[3] + sign * h
  sums[4] = sums[4] + sign * u * u
  sums[5] = sums[5] + sign * u * h
  sums[6] = sums[6] + sign * h * h
end

-- 采样一个雷达：有效则写入桶并增量更新回归和
local function sample_side(rid, d, buf, age, sums, fx, fy, wlo, whi)
  if (not rid) or rid == 0 then return end
  if (not d) or d <= 0.05 or d > 45 then return end
  local e = Entity(rid)
  if (not e) or e._nil or e:isValid() ~= 1 then return end
  local px, py = e:getPosition()
  local a = math.rad(e:getAngle())
  local hx = px + d * math.cos(a)
  local hy = py + d * math.sin(a)
  -- 世界前向坐标
  local uh = hx * fx + hy * fy
  if uh < wlo or uh > whi then return end
  local k = math.floor(uh / BIN + 0.000001)
  local old = buf[k]
  if old ~= nil then
    bin_add(sums, (k + 0.5) * BIN, old, -1)
  end
  buf[k] = hy
  age[k] = ntick
  bin_add(sums, (k + 0.5) * BIN, hy, 1)
end

-- 窗口滑动 + 按龄淘汰（增量减除）
local function evict(buf, age, sums, k_lo, maxage)
  for k, h in pairs(buf) do
    if k < k_lo or (ntick - age[k]) > maxage then
      bin_add(sums, (k + 0.5) * BIN, h, -1)
      buf[k] = nil
      age[k] = nil
    end
  end
end

-- 残差RMS、回归斜率、拟合R2
local function fit_sigma(sums)
  local n, Su, Sh, Suu, Suh, Shh = sums[1], sums[2], sums[3], sums[4], sums[5], sums[6]
  if n < MIN_N then return nil, nil, nil end
  local den = n * Suu - Su * Su
  if math.abs(den) < 1e-9 then return nil, nil, nil end
  local b = (n * Suh - Su * Sh) / den
  local a = (Sh - b * Su) / n
  local v = (Shh - a * Sh - b * Suh) / n
  if v < 0 then v = 0 end
  local syy = Shh - Sh * Sh / n
  local r2
  if syy < 1e-6 then r2 = 1.0 else r2 = 1.0 - (v * n) / syy end
  return math.sqrt(v), b, r2
end

function OnTick()
  local body = Entity(inputs.entity.body)
  if (not body) or body._nil or body:isValid() ~= 1 then
    outputs.string.status = "body not wired"
    return
  end
  local bx, by = body:getPosition()
  local ba = math.rad(body:getAngle())
  local fx, fy = math.cos(ba), math.sin(ba)
  local ub = bx * fx + by * fy
  local wlo = ub + NEAR
  local whi = ub + FAR
  local k_lo = math.floor(wlo / BIN)

  local maxage = inputs.num.maxage or 720  -- 桶淘汰年龄(720 tick = 180tps下4秒)

  sample_side(inputs.entity.ranger1, inputs.num.r1dist, bufL, ageL, sumL, fx, fy, wlo, whi)
  sample_side(inputs.entity.ranger2, inputs.num.r2dist, bufR, ageR, sumR, fx, fy, wlo, whi)

  ntick = ntick + 1
  evict(bufL, ageL, sumL, k_lo, maxage)
  evict(bufR, ageR, sumR, k_lo, maxage)

  if (ntick % UPDATE_EVERY) ~= 0 then return end

  local sL, bL, qL = fit_sigma(sumL)
  local sR, bR, qR = fit_sigma(sumR)
  if (not sL) or (not sR) then
    outputs.num.score = 0.0
    outputs.num.slope = 0.0
    outputs.num.pothole = 0.0
    outputs.num.roll = 0.0
    outputs.string.status = "low conf"
    return
  end
  outputs.num.score = (sL + sR) * 0.5
  -- R2 拟合质量门控：数据被坑遮挡/混杂时冻结坡度，防止把台阶误读成坡
  if qL >= 0.7 and qR >= 0.7 then
    last_slope = math.deg(math.atan((bL + bR) * 0.5))
  end
  outputs.num.slope = last_slope

  -- 坑深与横滚：一次有界扫描(≤32桶×2)
  local aL = (sumL[3] - bL * sumL[2]) / sumL[1]
  local aR = (sumR[3] - bR * sumR[2]) / sumR[1]
  local pothole, rn, rs = 0.0, 0, 0.0
  local k_hi = k_lo + 28
  for k = k_lo, k_hi do
    local hl, hr = bufL[k], bufR[k]
    if hl and hr then
      local rl = math.abs(hl - (aL + bL * (k + 0.5) * BIN))
      local rr = math.abs(hr - (aR + bR * (k + 0.5) * BIN))
      if rl > pothole then pothole = rl end
      if rr > pothole then pothole = rr end
      local dv = hl - hr
      rs = rs + dv * dv
      rn = rn + 1
    end
  end
  outputs.num.pothole = pothole
  outputs.num.roll = (rn > 0) and math.sqrt(rs / rn) or 0.0
  outputs.string.status = "ok"
end
