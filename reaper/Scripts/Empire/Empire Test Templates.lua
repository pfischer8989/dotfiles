-- Empire Test Templates
-- Opens "Empire Song" in a new tab, inserts every Empire track template with
-- "Empire Insert Track" and writes the result (tracks, folders, sends, VCA
-- groups, FX) to Empire-test.log in the REAPER resource folder. Close the tab
-- without saving after.

local R = reaper
local RES = R.GetResourcePath()
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
local DIR = RES .. "/TrackTemplates/Empire"

R.Main_OnCommand(40859, 0) -- new project tab
R.Main_openProject("template:noprompt:" .. RES .. "/ProjectTemplates/Empire Song.RPP")

local names, i = {}, 0
while true do
  local f = R.EnumerateFiles(DIR, i)
  if not f then break end
  local n = f:match("^(.*)%.RTrackTemplate$")
  if n then names[#names + 1] = n end
  i = i + 1
end
table.sort(names)

for _, n in ipairs(names) do
  R.SetExtState("Empire", "insert", n, false)
  dofile(HERE .. "/Empire Insert Track.lua")
end

local out = {}
local function w(s) out[#out + 1] = s end
local function nm(tr)
  if tr == R.GetMasterTrack(0) then return "MASTER" end
  local _, n = R.GetSetMediaTrackInfo_String(tr, "P_NAME", "", false)
  return n
end
local function fx(tr)
  local t = {}
  for k = 0, R.TrackFX_GetCount(tr) - 1 do
    local _, f = R.TrackFX_GetFXName(tr, k, "")
    t[#t + 1] = f
  end
  return table.concat(t, " > ")
end

w("templates: " .. table.concat(names, ", "))
w("MASTER  fx: " .. fx(R.GetMasterTrack(0)))
local level = 0
for k = 0, R.CountTracks(0) - 1 do
  local tr = R.GetTrack(0, k)
  local d = R.GetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH")
  local line = string.rep("  ", level) .. nm(tr) .. "  [depth " .. math.floor(d) .. "]"
  local lead = R.GetSetTrackGroupMembership(tr, "VOLUME_VCA_LEAD", 0, 0)
  local follow = R.GetSetTrackGroupMembership(tr, "VOLUME_VCA_FOLLOW", 0, 0)
  if lead ~= 0 then line = line .. " vca-lead=" .. lead end
  if follow ~= 0 then line = line .. " vca-follow=" .. follow end
  if R.GetMediaTrackInfo_Value(tr, "I_RECARM") == 1 then line = line .. " ARMED" end
  if R.GetMediaTrackInfo_Value(tr, "B_MAINSEND") == 0 then line = line .. " no-parent-send" end
  local f = fx(tr)
  if f ~= "" then line = line .. "  fx: " .. f end
  for s = 0, R.GetTrackNumSends(tr, 0) - 1 do
    local dst = R.GetTrackSendInfo_Value(tr, 0, s, "P_DESTTRACK")
    local v = R.GetTrackSendInfo_Value(tr, 0, s, "D_VOL")
    local src = R.GetTrackSendInfo_Value(tr, 0, s, "I_SRCCHAN")
    line = line .. string.format("  -> %s %.0f dB (src %d)", nm(dst), 20 * math.log(v, 10), src)
  end
  w(line)
  level = level + d
end
w("final level " .. level)

local f = io.open(RES .. "/Empire-test.log", "w")
f:write(table.concat(out, "\n"), "\n")
f:close()
R.ShowConsoleMsg(table.concat(out, "\n") .. "\n")
