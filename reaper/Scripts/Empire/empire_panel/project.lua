-- Things the panel and the sketch scripts both do to the current project.

local R = reaper
local core = require("core")
local project = {}

function project.value(key)
  local _, value = R.GetProjExtState(0, "empire", key)
  return value
end

function project.is_empty()
  return R.CountTracks(0) == 0 and R.CountProjectMarkers(0) == 0
end

-- Scripts can only set the MIDI editor's root, through its key snap action,
-- and that needs an editor open. Uses the open one, or opens one on a throwaway
-- item and closes it again. Returns whether REAPER reports the new root.
local function set_midi_root(key)
  local action, root = core.key_action(key)
  local index = R.CountTracks(0)
  R.InsertTrackAtIndex(index, false)
  local track = R.GetTrack(0, index)
  local item = R.CreateNewMIDIItemInProj(track, 0, 1, true)
  local selected = {}
  for i = 0, R.CountSelectedMediaItems(0) - 1 do selected[#selected + 1] = R.GetSelectedMediaItem(0, i) end

  local editor = R.MIDIEditor_GetActive()
  local opened = false
  if not editor then
    R.SelectAllMediaItems(0, false)
    R.SetMediaItemSelected(item, true)
    R.Main_OnCommand(40153, 0) -- open in the built-in MIDI editor
    editor = R.MIDIEditor_GetActive()
    opened = editor ~= nil
  end
  local got = nil
  if editor then
    R.MIDIEditor_OnCommand(editor, action)
    got = R.MIDIEditor_GetSetting_int(editor, "scale_root")
    if opened then R.MIDIEditor_OnCommand(editor, 2) end -- close it
  end

  R.DeleteTrack(track)
  R.SelectAllMediaItems(0, false)
  for _, it in ipairs(selected) do R.SetMediaItemSelected(it, true) end
  R.UpdateArrange()
  return got == root
end

-- The key and scale live in the project; the notes show them to a person.
function project.set_key(key, scale)
  R.SetProjExtState(0, "empire", "key", key)
  R.SetProjExtState(0, "empire", "scale", scale)
  R.GetSetProjectNotes(0, true, core.notes_with_key(R.GetSetProjectNotes(0, false, ""), key, scale))
  return set_midi_root(key)
end

function project.set_tempo(doc)
  local ts = doc.time_signature
  local marker = R.CountTempoTimeSigMarkers(0) > 0 and 0 or -1
  R.SetTempoTimeSigMarker(0, marker, 0, -1, -1, doc.tempo, ts[1], ts[2], false)
  R.UpdateTimeline()
end

-- Inserts a track template through Empire Insert Track and returns the track
-- holding the instrument, which in a kit is a child of the folder.
function project.insert_template(here, name)
  R.SetExtState("Empire", "insert", name, false)
  dofile(here .. "/Empire Insert Track.lua")
  local first = nil
  for i = 0, R.CountSelectedTracks(0) - 1 do
    local track = R.GetSelectedTrack(0, i)
    first = first or track
    if R.TrackFX_GetInstrument(track) >= 0 then return track end
  end
  return first
end

-- The regions in project order: { name, start, stop }.
function project.regions()
  local out, i = {}, 0
  while true do
    local more, is_region, start, stop, name = R.EnumProjectMarkers3(0, i)
    if more == 0 then return out end
    if is_region then out[#out + 1] = { name = name, start = start, stop = stop } end
    i = i + 1
  end
end

-- Loops a region and, if playing, jumps there.
function project.loop_region(region)
  R.GetSetRepeat(1)
  R.GetSet_LoopTimeRange2(0, true, true, region.start, region.stop, false)
  R.SetEditCurPos2(0, region.start, false, R.GetPlayState() & 1 == 1)
end

return project
