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

-- Steps the MIDI editor's key signature until it reports the scale. The action
-- has no target, so it walks the list one way, then the other. Returns whether
-- it got there.
local function step_to_scale(editor, take, mask)
  local function now()
    local _, _, scale = R.MIDI_GetScale(take)
    return scale
  end
  for _, action in ipairs({ 40757, 40756 }) do -- next and previous key signature
    for _ = 1, 64 do
      if now() == mask then return true end
      R.MIDIEditor_OnCommand(editor, action)
    end
  end
  return now() == mask
end

-- The MIDI editor's key is one setting for every editor, set through its
-- actions, and that needs an editor open. Uses the open one, or opens one on a
-- throwaway item and closes it again. Returns whether REAPER reports the new
-- root, then the new scale.
local function set_midi_key(key, scale)
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
  local got, scale_ok = nil, false
  if editor then
    R.MIDIEditor_OnCommand(editor, action)
    got = R.MIDIEditor_GetSetting_int(editor, "scale_root")
    local mask, take = core.scale_mask(scale), R.MIDIEditor_GetTake(editor)
    if mask and take then scale_ok = step_to_scale(editor, take, mask) end
    if opened then R.MIDIEditor_OnCommand(editor, 2) end -- close it
  end

  R.DeleteTrack(track)
  R.SelectAllMediaItems(0, false)
  for _, it in ipairs(selected) do R.SetMediaItemSelected(it, true) end
  R.UpdateArrange()
  return got == root, scale_ok
end

-- Drum tracks get named rows and no key snap. REAPER remembers the mode per
-- take, but key snap and hiding rows are one setting for every editor, so those
-- come back on leaving a drum track. Choosing piano roll is what clears hiding.
-- The launcher calls this all the time.
local drum_view = { take = nil, inside = false, snap = false }
local PIANO_ROLL, NAMED_NOTES, HIDE_UNNAMED, KEY_SNAP = 40042, 40043, 40454, 42471

function project.update_drum_view()
  local editor = R.MIDIEditor_GetActive()
  if not editor then return end
  local take = R.MIDIEditor_GetTake(editor)
  if not take or take == drum_view.take or not R.ValidatePtr(take, "MediaItem_Take*") then return end
  drum_view.take = take
  local _, kit = R.GetSetMediaTrackInfo_String(R.GetMediaItemTake_Track(take), "P_EXT:empire_drums", "", false)
  local hidden = R.GetToggleCommandStateEx(32060, HIDE_UNNAMED) == 1
  local snapping = R.MIDIEditor_GetSetting_int(editor, "scale_enabled") == 1
  if kit ~= "" then
    if not drum_view.inside then
      drum_view.inside, drum_view.snap = true, snapping
    end
    if R.GetToggleCommandStateEx(32060, NAMED_NOTES) ~= 1 then R.MIDIEditor_OnCommand(editor, NAMED_NOTES) end
    if snapping then R.MIDIEditor_OnCommand(editor, KEY_SNAP) end
    if not hidden then R.MIDIEditor_OnCommand(editor, HIDE_UNNAMED) end
  elseif drum_view.inside then
    drum_view.inside = false
    if drum_view.snap and not snapping then R.MIDIEditor_OnCommand(editor, KEY_SNAP) end
    if R.GetToggleCommandStateEx(32060, NAMED_NOTES) ~= 1 then R.MIDIEditor_OnCommand(editor, PIANO_ROLL) end
  end
end

-- Names a kit's rows on a track and marks the track as drums.
function project.set_drum_kit(track, template)
  local kit = core.DRUM_KITS[template]
  if not kit then return false end
  for note, name in pairs(kit.names) do R.SetTrackMIDINoteNameEx(0, track, note, -1, name) end
  R.GetSetMediaTrackInfo_String(track, "P_EXT:empire_drums", template, true)
  return true
end

-- The key and scale live in the project; the notes show them to a person.
function project.set_key(key, scale)
  R.SetProjExtState(0, "empire", "key", key)
  R.SetProjExtState(0, "empire", "scale", scale)
  R.GetSetProjectNotes(0, true, core.notes_with_key(R.GetSetProjectNotes(0, false, ""), key, scale))
  return set_midi_key(key, scale)
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

-- Makes the selected clips of a sketch play in their own track and section,
-- and mutes the other options there. Nothing else changes.
function project.launch_selected()
  local loop_bars, sections = tonumber(project.value("loop_bars")), tonumber(project.value("sections"))
  if not loop_bars or not sections then return end
  local items, clips = {}, {}
  for i = 0, R.CountMediaItems(0) - 1 do
    local item = R.GetMediaItem(0, i)
    local _, bar = R.TimeMap2_timeToBeats(0, R.GetMediaItemInfo_Value(item, "D_POSITION"))
    items[#items + 1] = item
    clips[#clips + 1] = { track = R.GetMediaItemTrack(item), selected = R.IsMediaItemSelected(item),
                          section = core.sketch_section(bar, loop_bars, sections) }
  end
  local muted = core.launch_mutes(clips)
  for i, item in ipairs(items) do
    if muted[i] ~= nil then R.SetMediaItemInfo_Value(item, "B_MUTE", muted[i] and 1 or 0) end
  end
  R.UpdateArrange()
end

return project
