-- Empire Sketch Test
-- Builds empire_sketch/mini.json (no plugins), picks some clips, builds the
-- master and writes what it finds to ~/.empire/reaper/sketches/sketch-test.log.
-- Leaves two tabs open; close them without saving.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
local DIR = os.getenv("HOME") .. "/.empire/reaper/sketches"
R.RecursiveCreateDirectory(DIR, 0)
local mini = DIR .. "/mini-test.json"
do
  local from = io.open(HERE .. "/empire_sketch/mini.json", "r")
  local to = io.open(mini, "w")
  to:write(from:read("a"))
  from:close()
  to:close()
end

local out, passed = {}, true
local function check(name, got, want)
  local ok = got == want
  if type(want) == "number" and type(got) == "number" then ok = math.abs(got - want) < 0.001 end
  passed = passed and ok
  out[#out + 1] = string.format("%-4s %s: got %s, want %s", ok and "ok" or "FAIL", name, tostring(got), tostring(want))
end
local function track_named(name)
  for i = 0, R.CountTracks(0) - 1 do
    local track = R.GetTrack(0, i)
    local _, got = R.GetSetMediaTrackInfo_String(track, "P_NAME", "", false)
    if got == name then return track end
  end
end
local function take_name(item)
  local _, name = R.GetSetMediaItemTakeInfo_String(R.GetActiveTake(item), "P_NAME", "", false)
  return name
end

local ok, err = xpcall(function()
  R.SetExtState("Empire", "sketch", mini, false)
  dofile(HERE .. "/Empire Build Sketch.lua")
  local one, two = track_named("One"), track_named("Two")
  check("One has lanes", R.GetMediaTrackInfo_Value(one, "I_NUMFIXEDLANES"), 3)
  check("One clips", R.CountTrackMediaItems(one), 6)
  check("Two clips", R.CountTrackMediaItems(two), 3)
  check("tempo", R.Master_GetTempo(), 120)
  local _, _, regions = R.CountProjectMarkers(0)
  check("regions", regions, 2)
  check("repeat on", R.GetSetRepeat(-1), 1)

  -- the next section action moves the loop
  dofile(HERE .. "/Empire Sketch Next Section.lua")
  local start = R.GetSet_LoopTimeRange2(0, false, true, 0, 0, false)
  check("next section loops Drop", start, 4)
  dofile(HERE .. "/Empire Sketch Previous Section.lua")
  start = R.GetSet_LoopTimeRange2(0, false, true, 0, 0, false)
  check("previous section loops Intro", start, 0)

  local want = { ["Intro One B: b"] = true, ["Drop One A: a"] = true, ["Drop One C: c"] = true, ["Drop Two B: b"] = true }
  for i = 0, R.CountMediaItems(0) - 1 do
    local item = R.GetMediaItem(0, i)
    R.SetMediaItemSelected(item, want[take_name(item)] == true)
  end
  local sketch_proj = R.EnumProjects(-1)
  dofile(HERE .. "/Empire Build Master.lua")
  check("master is a new tab", R.EnumProjects(-1) ~= sketch_proj, true)

  one, two = track_named("One"), track_named("Two")
  check("master items", R.CountMediaItems(0), 4)
  check("One clips in master", R.CountTrackMediaItems(one), 3)
  check("Two clips in master", R.CountTrackMediaItems(two), 1)
  check("One layered on 2 lanes", R.GetMediaTrackInfo_Value(one, "I_NUMFIXEDLANES"), 2)
  check("Two has no lanes", R.GetMediaTrackInfo_Value(two, "I_FREEMODE"), 0)
  for i = 0, R.CountMediaItems(0) - 1 do
    local item = R.GetMediaItem(0, i)
    local name = take_name(item)
    local position, length = R.GetMediaItemInfo_Value(item, "D_POSITION"), R.GetMediaItemInfo_Value(item, "D_LENGTH")
    -- 2 s a bar at 120 BPM: Intro bars 0-4, Drop bars 4-12
    check(name .. " start", position, name:match("^Intro") and 0 or 8)
    check(name .. " length", length, name:match("^Intro") and 8 or 16)
    check(name .. " loops", R.GetMediaItemInfo_Value(item, "B_LOOPSRC"), 1)
  end
  local _, markers, regions_left = R.CountProjectMarkers(0)
  check("master markers", markers, 3)
  check("master regions", regions_left, 0)
  check("master key", ({ R.GetProjExtState(0, "empire", "key") })[2], "A")
  check("master role", ({ R.GetProjExtState(0, "empire", "role") })[2], "master")
  local _, sel_name = R.EnumProjects(-1)
  check("master saved under its own name", sel_name:match("master%-") ~= nil, true)
end, debug.traceback)
if not ok then
  passed = false
  out[#out + 1] = "ERROR " .. tostring(err)
end

local f = io.open(DIR .. "/sketch-test.log", "w")
f:write(os.date("%Y-%m-%d %H:%M:%S "), "REAPER ", R.GetAppVersion(), "\n", table.concat(out, "\n"), "\n", passed and "PASS\n" or "FAILED\n")
f:close()
