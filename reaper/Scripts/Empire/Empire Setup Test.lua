-- Empire Setup Test
-- What can a script set up in a new project? Opens a new project tab, tries
-- tempo, time signature, markers and every way of setting a key and scale, and
-- writes what it reads back to ~/.empire/reaper/setup-test.log. Close the tab
-- without saving.

local R = reaper
local dir = os.getenv("HOME") .. "/.empire/reaper"
R.RecursiveCreateDirectory(dir, 0)
local out = {}
local function say(...)
  local parts = {}
  for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
  out[#out + 1] = table.concat(parts, " ")
end

R.Main_OnCommand(40859, 0) -- new project tab

for _, name in ipairs({ "MIDI_GetScale", "MIDI_SetScale", "MIDIEditor_GetSetting_int",
                        "MIDIEditor_SetSetting_int", "GetProjectTimeSignature2", "SetTempoTimeSigMarker" }) do
  say("api", name, R.APIExists(name))
end

-- tempo and time signature
R.SetTempoTimeSigMarker(0, -1, 0, -1, -1, 142, 6, 8, false)
R.UpdateTimeline()
say("tempo markers", R.CountTempoTimeSigMarkers(0))
say("timesig", R.GetProjectTimeSignature2(0))
say("master tempo", R.Master_GetTempo())
say("TimeMap_GetTimeSigAtTime", R.TimeMap_GetTimeSigAtTime(0, 0))

-- markers at bars
for _, bar in ipairs({ 0, 16, 32 }) do
  local pos = R.TimeMap2_beatsToTime(0, 0, bar)
  R.AddProjectMarker2(0, false, pos, 0, "Bar " .. bar, -1, 0)
  say("marker at bar", bar, "time", pos)
end
say("marker count", R.CountProjectMarkers(0))
say("marker 2", R.EnumProjectMarkers3(0, 1))

-- a take's scale
R.InsertTrackAtIndex(0, true)
local track = R.GetTrack(0, 0)
local item = R.CreateNewMIDIItemInProj(track, 0, 4, true)
local take = R.GetActiveTake(item)
say("scale before", R.MIDI_GetScale(take))
if R.MIDI_SetScale then
  say("set scale", R.MIDI_SetScale(take, 6, 0x5AD, 0))
  say("scale after", R.MIDI_GetScale(take))
end
local _, chunk = R.GetItemStateChunk(item, "", false)
for line in chunk:gmatch("[^\n]+") do
  if line:match("CFGEDIT") or line:match("KEYSNAP") or line:match("SCALE") or line:match("SOURCE") then
    say("chunk", line)
  end
end

-- the MIDI editor's scale settings
local editor = R.MIDIEditor_GetActive()
say("active editor", editor)
R.Main_OnCommand(40297, 0)
R.SetMediaItemSelected(item, true)
R.Main_OnCommand(40153, 0) -- open in the built-in MIDI editor
editor = R.MIDIEditor_GetActive()
say("editor opened", editor)
if editor then
  for _, key in ipairs({ "scale_enabled", "scale_root", "scale_type", "snap_enabled" }) do
    say("editor", key, R.MIDIEditor_GetSetting_int(editor, key))
  end
  R.MIDIEditor_SetSetting_int(editor, "scale_root", 6)
  R.MIDIEditor_SetSetting_int(editor, "scale_enabled", 1)
  say("editor root after set", R.MIDIEditor_GetSetting_int(editor, "scale_root"))
  say("editor enabled after set", R.MIDIEditor_GetSetting_int(editor, "scale_enabled"))
  say("take scale after editor set", R.MIDI_GetScale(take))
  R.MIDIEditor_OnCommand(editor, 2) -- close
  _, chunk = R.GetItemStateChunk(item, "", false)
  for line in chunk:gmatch("[^\n]+") do
    if line:match("CFGEDIT") or line:match("KEYSNAP") or line:match("SCALE") then say("chunk after", line) end
  end
end

-- notes and project-level state
R.GetSetProjectNotes(0, true, "Key: F#\nScale: minor")
say("notes", (select(1, R.GetSetProjectNotes(0, false, ""))))
R.SetProjExtState(0, "empire", "key", "F#")
say("ext", R.GetProjExtState(0, "empire", "key"))

local f = io.open(dir .. "/setup-test.log", "w")
if f then
  f:write(os.date("%Y-%m-%d %H:%M:%S "), "REAPER ", R.GetAppVersion(), "\n", table.concat(out, "\n"), "\n")
  f:close()
end
