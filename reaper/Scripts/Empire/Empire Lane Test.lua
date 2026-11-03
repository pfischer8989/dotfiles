-- Empire Lane Test
-- Can a script put MIDI on REAPER 7 fixed item lanes and tag the takes? Opens a
-- new project tab, builds a track with three option lanes and writes what it
-- reads back to ~/.empire/reaper/lane-test.log. Close the tab without saving.

local R = reaper
local dir = os.getenv("HOME") .. "/.empire/reaper"
R.RecursiveCreateDirectory(dir, 0)

local out = {}
local passed = true
local function check(name, got, want)
  local ok = got == want
  passed = passed and ok
  out[#out + 1] = string.format("%-4s %s: got %s, want %s", ok and "ok" or "FAIL", name, tostring(got), tostring(want))
end

R.Main_OnCommand(40859, 0) -- new project tab
R.Undo_BeginBlock()
R.SetCurrentBPM(0, 140, false)
R.InsertTrackAtIndex(0, true)
local track = R.GetTrack(0, 0)
R.GetSetMediaTrackInfo_String(track, "P_NAME", "Lane Test", true)
R.SetMediaTrackInfo_Value(track, "I_FREEMODE", 2)
R.SetMediaTrackInfo_Value(track, "I_NUMFIXEDLANES", 3)

local BAR = 4 * 60 / 140
local OPTIONS = { { name = "A", pitch = 36 }, { name = "B", pitch = 38 }, { name = "C", pitch = 42 } }
local items = {}
for i, option in ipairs(OPTIONS) do
  local lane = i - 1
  local item = R.CreateNewMIDIItemInProj(track, 0, BAR, false)
  R.SetMediaItemInfo_Value(item, "I_FIXEDLANE", lane)
  R.GetSetMediaTrackInfo_String(track, "P_LANENAME:" .. lane, "Option " .. option.name, true)
  local take = R.GetActiveTake(item)
  for beat = 0, 3 do
    R.MIDI_InsertNote(take, false, false, beat * 960, beat * 960 + 480, 9, option.pitch, 100, true)
  end
  R.MIDI_Sort(take)
  R.GetSetMediaItemTakeInfo_String(take, "P_EXT:empire_ids", "option-" .. option.name, true)
  items[i] = item
end
-- Only option A plays; the others stay in the project, muted by their lanes.
R.SetMediaTrackInfo_Value(track, "C_LANEPLAYS:0", 1)
R.TrackList_AdjustWindows(false)
R.UpdateArrange()
R.Undo_EndBlock("Empire lane test", -1)

check("track mode is fixed lanes", R.GetMediaTrackInfo_Value(track, "I_FREEMODE"), 2.0)
check("lane count", R.GetMediaTrackInfo_Value(track, "I_NUMFIXEDLANES"), 3.0)
check("lane A plays", R.GetMediaTrackInfo_Value(track, "C_LANEPLAYS:0"), 1.0)
check("lane B silent", R.GetMediaTrackInfo_Value(track, "C_LANEPLAYS:1"), 0.0)
for i, option in ipairs(OPTIONS) do
  local take = R.GetActiveTake(items[i])
  check(option.name .. " lane", R.GetMediaItemInfo_Value(items[i], "I_FIXEDLANE"), i - 1.0)
  local _, notes = R.MIDI_CountEvts(take)
  check(option.name .. " note count", notes, 4)
  local _, _, _, _, _, _, pitch = R.MIDI_GetNote(take, 0)
  check(option.name .. " pitch", pitch, option.pitch)
  local _, tag = R.GetSetMediaItemTakeInfo_String(take, "P_EXT:empire_ids", "", false)
  check(option.name .. " tag", tag, "option-" .. option.name)
  local _, lane = R.GetSetMediaTrackInfo_String(track, "P_LANENAME:" .. (i - 1), "", false)
  check(option.name .. " lane name", lane, "Option " .. option.name)
end

local f = io.open(dir .. "/lane-test.log", "w")
if f then
  f:write(os.date("%Y-%m-%d %H:%M:%S "), "REAPER ", R.GetAppVersion(), "\n")
  f:write(table.concat(out, "\n"), "\n", passed and "PASS\n" or "FAILED\n")
  f:close()
end
