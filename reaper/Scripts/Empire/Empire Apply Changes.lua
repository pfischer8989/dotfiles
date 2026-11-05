-- Empire Apply Changes
-- empire_sketch/apply_changes.py works out which clips a list of changes rewrites,
-- copies the newest master to a new dated file and names it in a request file. This
-- opens that copy in a new tab, swaps the clips and saves it. The old master isn't
-- touched. It answers in a result file instead of showing a message.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local core = require("core")

local SKETCHES = os.getenv("HOME") .. "/.empire/reaper/sketches"
local REQUEST, RESULT = SKETCHES .. "/apply-request.json", SKETCHES .. "/apply-result.json"
local PPQ = 960

local function answer(fields)
  local f = io.open(RESULT .. ".tmp", "w")
  if not f then return end
  f:write(core.json_encode(fields))
  f:close()
  os.rename(RESULT .. ".tmp", RESULT)
end

local function read_request()
  local f = io.open(REQUEST, "r")
  if not f then return nil end
  local text = f:read("a")
  f:close()
  os.remove(REQUEST)
  return core.json_decode(text)
end

-- The base was read from disk, so changes not saved yet would be silently lost.
local function has_unsaved_changes(path)
  local i = 0
  while true do
    local tab, file = R.EnumProjects(i)
    if not tab then return false end
    if file == path and R.IsProjectDirty(tab) == 1 then return true end
    i = i + 1
  end
end

local function find_track(name)
  for i = 0, R.CountTracks(0) - 1 do
    local track = R.GetTrack(0, i)
    local _, track_name = R.GetSetMediaTrackInfo_String(track, "P_NAME", "", false)
    if track_name == name then return track end
  end
  return nil
end

local function remove_clips(track, start, stop)
  for i = R.CountTrackMediaItems(track) - 1, 0, -1 do
    local item = R.GetTrackMediaItem(track, i)
    local at = R.GetMediaItemInfo_Value(item, "D_POSITION")
    if at >= start - 0.001 and at < stop - 0.001 then R.DeleteTrackMediaItem(track, item) end
  end
end

local function write_clip(track, entry)
  local start = R.TimeMap2_beatsToTime(0, 0, entry.first_bar - 1)
  local stop = R.TimeMap2_beatsToTime(0, 0, entry.first_bar - 1 + entry.bars)
  remove_clips(track, start, stop)
  if #entry.notes == 0 then return end
  local start_qn = R.TimeMap2_timeToQN(0, start)
  local source_stop = entry.loop_bars and R.TimeMap2_beatsToTime(0, 0, entry.first_bar - 1 + entry.loop_bars) or stop
  local item = R.CreateNewMIDIItemInProj(track, start_qn, R.TimeMap2_timeToQN(0, source_stop), true)
  local take = R.GetActiveTake(item)
  for _, n in ipairs(entry.notes) do
    local on = R.MIDI_GetPPQPosFromProjQN(take, start_qn + n[1] / PPQ)
    local off = R.MIDI_GetPPQPosFromProjQN(take, start_qn + (n[1] + n[4]) / PPQ)
    R.MIDI_InsertNote(take, false, false, on, off, n[3], n[2], n[5], true)
  end
  R.MIDI_Sort(take)
  R.GetSetMediaItemTakeInfo_String(take, "P_NAME", entry.name, true)
  R.SetMediaItemInfo_Value(item, "B_LOOPSRC", entry.loop_bars and 1 or 0)
  R.SetMediaItemInfo_Value(item, "D_LENGTH", stop - start)
end

local function apply(request)
  if has_unsaved_changes(request.base) then
    return answer({ ok = false, message = "The master has unsaved changes in REAPER. Save it, then try again." })
  end
  R.Main_OnCommand(40859, 0) -- new project tab
  R.Main_openProject("noprompt:" .. request.master)
  local _, open_file = R.EnumProjects(-1)
  if open_file ~= request.master then
    return answer({ ok = false, message = "REAPER didn't open " .. request.master })
  end
  for _, entry in ipairs(request.entries) do
    if not find_track(entry.part) then
      return answer({ ok = false, message = "no track called " .. entry.part })
    end
  end
  R.Undo_BeginBlock()
  R.PreventUIRefresh(1)
  for _, entry in ipairs(request.entries) do write_clip(find_track(entry.part), entry) end
  R.PreventUIRefresh(-1)
  R.UpdateArrange()
  R.Undo_EndBlock("Empire: apply changes", -1)
  R.Main_SaveProject(0, false)
  answer({ ok = true, master = request.master, clips = #request.entries })
end

local ok, request = pcall(read_request)
if not ok then
  answer({ ok = false, message = "can't read the request: " .. tostring(request) })
elseif request then
  apply(request)
end
