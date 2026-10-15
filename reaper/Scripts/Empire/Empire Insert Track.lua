-- Empire Insert Track
-- Pick an Empire track template from a menu at the mouse; it's inserted into
-- its folder bus (DRUMS, SYNTHS, GTR, AMBIENT), joins that section's VCA
-- group, gets its sends to the returns (Verb Short, Verb Long, Shimmer, Delay,
-- Drum Crush) and is armed if it records audio. Built for the "Empire Song"
-- project template; in other projects whatever it can't find is skipped.
--
-- The wiring is read from each template track's P_EXT:empire:
--   folder=NAME;vca=NAME;sends=Return:dB,Return:dB;arm=1

local R = reaper
local DIR = R.GetResourcePath() .. "/TrackTemplates/Empire"

local function templates()
  local names, i = {}, 0
  while true do
    local f = R.EnumerateFiles(DIR, i)
    if not f then break end
    local n = f:match("^(.*)%.RTrackTemplate$")
    if n then names[#names + 1] = n end
    i = i + 1
  end
  table.sort(names)
  return names
end

local function pick(names)
  local x, y = R.GetMousePosition()
  gfx.init("Empire", 0, 0, 0, x, y)
  gfx.x, gfx.y = gfx.screentoclient(x, y)
  local c = gfx.showmenu(table.concat(names, "|"))
  gfx.quit()
  return names[c]
end

local function ext(tr)
  local _, s = R.GetSetMediaTrackInfo_String(tr, "P_EXT:empire", "", false)
  local t = {}
  for k, v in s:gmatch("([%w_]+)=([^;]*)") do t[k] = v end
  return t
end

local function name(tr)
  local _, n = R.GetSetMediaTrackInfo_String(tr, "P_NAME", "", false)
  return n
end

local function depth(tr) return R.GetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH") end
local function set_depth(tr, d) R.SetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH", d) end

-- Top-level track called `n` (folders and returns are top level or in FX).
local function find(n, skip)
  for i = 0, R.CountTracks(0) - 1 do
    local tr = R.GetTrack(0, i)
    if not skip[tr] and name(tr) == n then return tr, i end
  end
end

local function index_of(tr) return R.GetMediaTrackInfo_Value(tr, "IP_TRACKNUMBER") - 1 end

-- Index after folder track fi's last child, and whether it has children.
local function region_end(fi)
  if depth(R.GetTrack(0, fi)) <= 0 then return fi + 1, false end
  local level, n = 1, R.CountTracks(0)
  for i = fi + 1, n - 1 do
    level = level + depth(R.GetTrack(0, i))
    if level <= 0 then return i + 1, true end
  end
  return n, true
end

local function group_bit(n)
  for g = 1, 32 do
    local _, gn = R.GetSetProjectInfo_String(0, "TRACK_GROUP_NAME:" .. g, "", false)
    if gn == n then return 1 << (g - 1) end
  end
end

local function insert(tmpl)
  local before = {}
  for i = 0, R.CountTracks(0) - 1 do before[R.GetTrack(0, i)] = true end

  -- Insert after the first track (a top-level VCA lead in Empire Song), so
  -- the new block starts out at the top level.
  R.Main_OnCommand(40297, 0) -- unselect all tracks
  if R.CountTracks(0) > 0 then
    local first = R.GetTrack(0, 0)
    R.SetTrackSelected(first, true)
    R.SetOnlyTrackSelected(first)
  end
  R.Main_openProject(DIR .. "/" .. tmpl .. ".RTrackTemplate")

  local block = {}
  for i = 0, R.CountTracks(0) - 1 do
    local tr = R.GetTrack(0, i)
    if not before[tr] then block[#block + 1] = tr end
  end
  if #block == 0 then return end
  local isnew = {}
  for _, tr in ipairs(block) do isnew[tr] = true end

  -- Which block tracks sit at the block's top level.
  local top, level = {}, 0
  for _, tr in ipairs(block) do
    if level == 0 then top[#top + 1] = tr end
    level = level + depth(tr)
  end

  local spec = ext(block[1])

  -- Move into the folder bus.
  local folder = spec.folder and find(spec.folder, isnew)
  if folder then
    local fi = index_of(folder)
    local stop, had = region_end(fi)
    R.Main_OnCommand(40297, 0)
    for _, tr in ipairs(block) do R.SetTrackSelected(tr, true) end
    R.ReorderSelectedTracks(stop, 0)
    local last = block[#block]
    local prev = R.GetTrack(0, index_of(block[1]) - 1)
    if had then
      set_depth(prev, depth(prev) + 1)
    else
      set_depth(folder, 1)
    end
    set_depth(last, depth(last) - 1)
  end

  -- VCA: the section's group, on the block's top-level tracks.
  local bit = spec.vca and group_bit(spec.vca)
  if bit then
    for _, tr in ipairs(top) do
      R.GetSetTrackGroupMembership(tr, "VOLUME_VCA_FOLLOW", bit, bit)
    end
  end

  -- Sends and arming, per track.
  for _, tr in ipairs(block) do
    local e = ext(tr)
    for ret, db in (e.sends or ""):gmatch("([^:,]+):([^,]+)") do
      local dst = find(ret, isnew)
      if dst then
        local s = R.CreateTrackSend(tr, dst)
        local v = tonumber(db)
        R.SetTrackSendInfo_Value(tr, 0, s, "D_VOL", v and 10 ^ (v / 20) or 0)
      end
    end
    if e.arm == "1" then R.SetMediaTrackInfo_Value(tr, "I_RECARM", 1) end
  end

  R.Main_OnCommand(40297, 0)
  for _, tr in ipairs(block) do R.SetTrackSelected(tr, true) end
  R.SetMixerScroll(block[1])
end

-- A test or another script can name the template instead of the menu.
local tmpl = R.GetExtState("Empire", "insert")
if tmpl ~= "" then
  R.DeleteExtState("Empire", "insert", false)
else
  local names = templates()
  if #names == 0 then
    R.ShowMessageBox("No templates in " .. DIR .. ". Run Empire Build Templates first.", "Empire", 0)
    return
  end
  tmpl = pick(names)
end
if not tmpl then return end

R.Undo_BeginBlock()
R.PreventUIRefresh(1)
insert(tmpl)
R.PreventUIRefresh(-1)
R.TrackList_AdjustWindows(false)
R.Undo_EndBlock("Empire: insert " .. tmpl, -1)
