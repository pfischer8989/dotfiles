-- Empire Build Master
-- Makes a master from what's playing in an Empire sketch: a new tab with only
-- the unmuted clips, each looped over its section's full length, on the same
-- tracks and plugins. The sketch isn't changed. Two clips on one track and
-- section are layered on lanes that all play.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local core = require("core")
local project = require("project")

local function say(text)
  R.ShowMessageBox(text, "Empire Build Master", 0)
end

local function read_doc(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local text = f:read("a")
  f:close()
  local ok, doc = pcall(core.json_decode, text)
  return ok and core.check_sketch(doc) or nil
end

local function build()
  local path = project.value("sketch")
  if path == "" or project.value("role") ~= "sketch" then
    return say("Switch to the sketch tab first.")
  end
  local playing = 0
  for i = 0, R.CountMediaItems(0) - 1 do
    if R.GetMediaItemInfo_Value(R.GetMediaItem(0, i), "B_MUTE") == 0 then playing = playing + 1 end
  end
  if playing == 0 then return say("Every clip is muted, so there's nothing to build from.") end
  local doc = read_doc(path)
  if not doc then return say("Can't read the sketch file:\n" .. path) end

  local master = path:gsub("[^/]+$", "") .. "master-" .. os.date("%Y%m%d-%H%M%S") .. ".RPP"
  R.Main_SaveProjectEx(0, master, 0) -- a copy; mutes and plugin state come along
  R.Main_OnCommand(40859, 0) -- new project tab
  R.Main_openProject("noprompt:" .. master)
  R.SetProjExtState(0, "empire", "role", "master") -- the launcher leaves a master alone

  R.Undo_BeginBlock()
  R.PreventUIRefresh(1)
  for i = R.CountMediaItems(0) - 1, 0, -1 do
    local item = R.GetMediaItem(0, i)
    if R.GetMediaItemInfo_Value(item, "B_MUTE") ~= 0 then
      R.DeleteTrackMediaItem(R.GetMediaItemTrack(item), item)
    end
  end

  local sections = doc.setup.sections
  local starts, total = core.section_bars(doc.setup)
  local picks, items = {}, {}
  for i = 0, R.CountMediaItems(0) - 1 do
    local item = R.GetMediaItem(0, i)
    local _, bar = R.TimeMap2_timeToBeats(0, R.GetMediaItemInfo_Value(item, "D_POSITION"))
    items[#items + 1] = item
    picks[#picks + 1] = { track = R.GetMediaItemTrack(item), section = core.sketch_section(bar, doc.loop_bars, #sections) }
  end
  local lanes, needed = core.master_lanes(picks)

  for i, item in ipairs(items) do
    local section = picks[i].section
    local start = R.TimeMap2_beatsToTime(0, 0, starts[section])
    local stop = R.TimeMap2_beatsToTime(0, 0, starts[section] + sections[section].bars)
    R.SetMediaItemInfo_Value(item, "D_POSITION", start)
    R.SetMediaItemInfo_Value(item, "D_LENGTH", stop - start)
    R.SetMediaItemInfo_Value(item, "B_LOOPSRC", 1)
    R.SetMediaItemInfo_Value(item, "I_FIXEDLANE", lanes[i])
  end

  -- a track gets the lanes it needs, all playing, or stops using lanes
  for i = 0, R.CountTracks(0) - 1 do
    local track = R.GetTrack(0, i)
    if R.GetMediaTrackInfo_Value(track, "I_FREEMODE") == 2 then
      local count = needed[track] or 0
      if count > 1 then
        R.SetMediaTrackInfo_Value(track, "I_NUMFIXEDLANES", count)
        for lane = 0, count - 1 do
          R.SetMediaTrackInfo_Value(track, "C_LANEPLAYS:" .. lane, 2)
        end
      else
        R.SetMediaTrackInfo_Value(track, "I_FREEMODE", 0)
      end
    end
  end

  for i = R.CountProjectMarkers(0) - 1, 0, -1 do R.DeleteProjectMarkerByIndex(0, i) end
  for i, section in ipairs(sections) do
    R.AddProjectMarker2(0, false, R.TimeMap2_beatsToTime(0, 0, starts[i]), 0, section.name, -1, 0)
  end
  local stop = R.TimeMap2_beatsToTime(0, 0, total)
  R.AddProjectMarker2(0, false, stop, 0, "End", -1, 0)
  R.GetSetRepeat(0)
  R.GetSet_LoopTimeRange2(0, true, true, 0, 0, false)
  R.SetEditCurPos2(0, 0, false, false)
  R.SelectAllMediaItems(0, false)
  R.GetSet_ArrangeView2(0, true, 0, 0, 0, stop)
  R.PreventUIRefresh(-1)
  R.TrackList_AdjustWindows(false)
  R.UpdateArrange()
  R.Undo_EndBlock("Empire: build master", -1)
  R.Main_SaveProject(0, false)
end

build()
