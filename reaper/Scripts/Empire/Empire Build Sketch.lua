-- Empire Build Sketch
-- Builds an idea board from a sketch file: one short loop per song section, in
-- its own region, and a track per part with a fixed lane per option. Loop a
-- section and switch lanes as it plays, then select the clips you like and run
-- Empire Build Master. Reads the file named by ~/.empire/reaper/sketches/latest.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local core = require("core")
local project = require("project")

local SKETCHES = os.getenv("HOME") .. "/.empire/reaper/sketches"
local COLORS = { R.ColorToNative(92, 140, 214), R.ColorToNative(224, 160, 70), R.ColorToNative(120, 190, 120),
                 R.ColorToNative(190, 110, 190) }

local function fail(text)
  R.ShowConsoleMsg("Empire Build Sketch: " .. text .. "\n")
end

local function read_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local text = f:read("a")
  f:close()
  return text
end

local function write_log(text)
  local f = io.open(SKETCHES .. "/sketch.log", "a")
  if f then
    f:write(os.date("%Y-%m-%d %H:%M:%S "), text, "\n")
    f:close()
  end
end

local function insert_clip(track, clip, start_qn, length_qn, ppq, lane)
  local item = R.CreateNewMIDIItemInProj(track, start_qn, start_qn + length_qn, true)
  R.SetMediaItemInfo_Value(item, "I_FIXEDLANE", lane)
  R.SetMediaItemInfo_Value(item, "B_LOOPSRC", 1)
  R.SetMediaItemInfo_Value(item, "I_CUSTOMCOLOR", COLORS[lane % #COLORS + 1] | 0x1000000)
  local take = R.GetActiveTake(item)
  for _, n in ipairs(clip.notes) do
    local on = R.MIDI_GetPPQPosFromProjQN(take, start_qn + n[1] / ppq)
    local off = R.MIDI_GetPPQPosFromProjQN(take, start_qn + (n[1] + n[4]) / ppq)
    R.MIDI_InsertNote(take, false, false, on, off, n[3], n[2], n[5], true)
  end
  R.MIDI_Sort(take)
  local name = string.format("%s %s %s%s", clip.section, clip.part, clip.option,
    clip.label and (": " .. clip.label) or "")
  R.GetSetMediaItemTakeInfo_String(take, "P_NAME", name, true)
  R.GetSetMediaItemTakeInfo_String(take, "P_EXT:empire_ids", clip.section .. "/" .. clip.part .. "/" .. clip.option, true)
end

local function register_scripts()
  for _, name in ipairs({ "Empire Build Master", "Empire Sketch Next Section", "Empire Sketch Previous Section" }) do
    R.AddRemoveReaScript(true, 0, HERE .. "/" .. name .. ".lua", true)
  end
end

local function build(path, doc)
  local started = R.time_precise()
  local setup = doc.setup
  local template = R.GetResourcePath() .. "/ProjectTemplates/Empire Song.RPP"
  if not R.file_exists(template) then return fail("run Empire Build Templates first") end
  for _, part in ipairs(doc.parts) do
    if part.template and not R.file_exists(R.GetResourcePath() .. "/TrackTemplates/Empire/" .. part.template .. ".RTrackTemplate") then
      return fail("no track template called " .. part.template)
    end
  end

  if not project.is_empty() then R.Main_OnCommand(40859, 0) end -- new project tab
  R.Main_openProject("template:noprompt:" .. template)
  project.set_tempo(setup)
  local loaded = R.time_precise()

  local tracks = {}
  for _, part in ipairs(doc.parts) do
    local track
    if part.template then
      track = project.insert_template(HERE, part.template)
    else
      R.InsertTrackAtIndex(R.CountTracks(0), true)
      track = R.GetTrack(0, R.CountTracks(0) - 1)
    end
    R.GetSetMediaTrackInfo_String(track, "P_NAME", part.name, true)
    R.SetMediaTrackInfo_Value(track, "I_FREEMODE", 2)
    R.SetMediaTrackInfo_Value(track, "I_NUMFIXEDLANES", doc.options)
    tracks[part.name] = track
  end
  local plugins = R.time_precise()

  R.Undo_BeginBlock()
  R.PreventUIRefresh(1)
  local bar_qn = setup.time_signature[1] * 4 / setup.time_signature[2]
  local section_index = {}
  for i, section in ipairs(setup.sections) do
    section_index[section.name] = i
    local first, last = (i - 1) * doc.loop_bars, i * doc.loop_bars
    R.AddProjectMarker2(0, true, R.TimeMap2_beatsToTime(0, 0, first), R.TimeMap2_beatsToTime(0, 0, last), section.name, -1, 0)
  end
  for _, clip in ipairs(doc.clips) do
    local start_qn = (section_index[clip.section] - 1) * doc.loop_bars * bar_qn
    insert_clip(tracks[clip.part], clip, start_qn, doc.loop_bars * bar_qn, doc.ppq, core.option_lane(clip.option, doc.options))
  end
  for _, track in pairs(tracks) do
    for lane = 0, doc.options - 1 do
      R.GetSetMediaTrackInfo_String(track, "P_LANENAME:" .. lane, string.char(65 + lane), true)
    end
    R.SetMediaTrackInfo_Value(track, "C_LANEPLAYS:0", 1)
  end
  R.SelectAllMediaItems(0, false)
  R.PreventUIRefresh(-1)
  R.Undo_EndBlock("Empire: build sketch", -1)

  local root_ok = project.set_key(setup.key, setup.scale)
  R.SetProjExtState(0, "empire", "sketch", path)
  R.SetProjExtState(0, "empire", "role", "sketch")
  local regions = project.regions()
  project.loop_region(regions[1])
  R.GetSet_ArrangeView2(0, true, 0, 0, 0, regions[#regions].stop)
  R.TrackList_AdjustWindows(false)
  R.UpdateArrange()
  register_scripts()
  local now = R.time_precise()
  write_log(string.format("built %s: %d clips, %d parts, midi root %s; template %.1fs, plugins %.1fs, clips %.1fs",
    path, #doc.clips, #doc.parts, root_ok and "set" or "not set", loaded - started, plugins - loaded, now - plugins))
end

local path = R.GetExtState("Empire", "sketch")
if path ~= "" then
  R.DeleteExtState("Empire", "sketch", false)
else
  path = (read_file(SKETCHES .. "/latest") or ""):gsub("%s+$", "")
end
local text = read_file(path)
if not text then
  fail("can't read a sketch at '" .. path .. "'")
else
  local ok, decoded = pcall(core.json_decode, text)
  local doc, err = nil, tostring(decoded)
  if ok then doc, err = core.check_sketch(decoded) end
  if doc then build(path, doc) else fail(path .. ": " .. tostring(err)) end
end
