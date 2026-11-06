-- Empire Mix
-- empire_sketch/mix.py names a job in a request file, and this does it in the open
-- REAPER, answering in a result file instead of showing a message.
--
-- bounce: opens a copy of a master in a new tab and prints each source track, after
-- its plugins and fader. The copy becomes the mix session: those tracks play the
-- audio at unity with no plugins, and buses, returns, sends, VCAs, markers and the
-- master chain stay live. The master isn't touched.
--
-- print: prints the saved mix session as it stands, tracks and returns, plus the
-- full mix through the master chain, so mix_check.py can measure them.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local core = require("core")

local SKETCHES = os.getenv("HOME") .. "/.empire/reaper/sketches"
local REQUEST, RESULT = SKETCHES .. "/mix-request.json", SKETCHES .. "/mix-result.json"
local TAIL_SECONDS = 5
local FLOAT_WAV = "ZXZhdyAAAQ==" -- WAV, 32-bit float, so nothing clips on the way out
local SILENT_GAIN = 10 ^ (90 / 20) -- a file this far below full scale has nothing in it
local FADER_ENVELOPES = { "Volume", "Pan", "Width", "Mute", "Trim Volume",
  "Volume (Pre-FX)", "Pan (Pre-FX)", "Width (Pre-FX)" }

local function write_json(path, fields)
  local f = io.open(path .. ".tmp", "w")
  if not f then return end
  f:write(core.json_encode(fields))
  f:close()
  os.rename(path .. ".tmp", path)
end

local function answer(fields) write_json(RESULT, fields) end

local function read_request()
  local f = io.open(REQUEST, "r")
  if not f then return nil end
  local text = f:read("a")
  f:close()
  os.remove(REQUEST)
  return core.json_decode(text)
end

local function find_tab(path)
  local i = 0
  while true do
    local tab, file = R.EnumProjects(i)
    if not tab then return nil end
    if file == path then return tab end
    i = i + 1
  end
end

local function name_of(track)
  local _, name = R.GetSetMediaTrackInfo_String(track, "P_NAME", "", false)
  return name
end

local function has_live_items(track)
  for i = 0, R.CountTrackMediaItems(track) - 1 do
    if R.GetMediaItemInfo_Value(R.GetTrackMediaItem(track, i), "B_MUTE") == 0 then return true end
  end
  return false
end

-- "source" plays something of its own, "return" is a live effect in the FX folder.
-- Buses, VCA leads, muted tracks and empty tracks aren't printed.
local function role_of(track)
  if R.GetMediaTrackInfo_Value(track, "I_FOLDERDEPTH") == 1 then return nil end
  if R.GetMediaTrackInfo_Value(track, "B_MUTE") == 1 then return nil end
  local in_fx = false
  local parent = R.GetParentTrack(track)
  while parent do
    if R.GetMediaTrackInfo_Value(parent, "B_MUTE") == 1 then return nil end
    if name_of(parent) == "FX" then in_fx = true end
    parent = R.GetParentTrack(parent)
  end
  local receives = R.GetTrackNumSends(track, -1) > 0
  if in_fx then return receives and "return" or nil end
  if has_live_items(track) or receives then return "source" end
  return nil
end

-- What the folder faders above a track add, since a track's print stops before them.
local function bus_gain_db(track)
  local gain = 1
  local parent = R.GetParentTrack(track)
  while parent do
    gain = gain * R.GetMediaTrackInfo_Value(parent, "D_VOL")
    parent = R.GetParentTrack(parent)
  end
  return 20 * math.log(gain, 10)
end

local function song_times()
  local markers, song_end = {}, nil
  local i = 0
  while true do
    local more, is_region, at, _, name = R.EnumProjectMarkers3(0, i)
    if more == 0 then break end
    if not is_region then
      if name:lower() == "end" then song_end = at else markers[#markers + 1] = { name = name, time = at } end
    end
    i = i + 1
  end
  song_end = song_end or R.GetProjectLength(0)
  local bars, bar = {}, 0
  while true do
    local at = R.TimeMap2_beatsToTime(0, 0, bar)
    if at >= song_end - 0.001 then break end
    bars[#bars + 1] = at
    bar = bar + 1
  end
  return markers, song_end, bars
end

local function wav_files(folder)
  local out, i = {}, 0
  R.EnumerateFiles(folder, -1) -- forget what REAPER remembers about this folder
  while true do
    local name = R.EnumerateFiles(folder, i)
    if not name then return out end
    if name:lower():match("%.wav$") then out[#out + 1] = name end
    i = i + 1
  end
end

-- Renders the given tracks in the current project to a folder, keeping the project's
-- own render settings and track selection. Returns track number -> file, and the
-- master mix's file when with_mix is set.
local function render(tracks, folder, stop_at, with_mix)
  R.RecursiveCreateDirectory(folder, 0)
  local selected = {}
  for i = 0, R.CountTracks(0) - 1 do
    local t = R.GetTrack(0, i)
    selected[i] = R.IsTrackSelected(t)
    R.SetTrackSelected(t, false)
  end
  for _, t in ipairs(tracks) do R.SetTrackSelected(t, true) end

  local numbers = { RENDER_SETTINGS = with_mix and 1 or 2, RENDER_BOUNDSFLAG = 0, RENDER_STARTPOS = 0,
    RENDER_ENDPOS = stop_at + TAIL_SECONDS, RENDER_CHANNELS = 2, RENDER_SRATE = 0, RENDER_ADDTOPROJ = 0,
    RENDER_NORMALIZE = 0, RENDER_DITHER = 0, RENDER_TAILFLAG = 0 }
  local strings = { RENDER_FILE = folder, RENDER_PATTERN = "$tracknumber", RENDER_FORMAT = FLOAT_WAV }
  local old_numbers, old_strings = {}, {}
  for key, value in pairs(numbers) do
    old_numbers[key] = R.GetSetProjectInfo(0, key, 0, false)
    R.GetSetProjectInfo(0, key, value, true)
  end
  for key, value in pairs(strings) do
    local _, old = R.GetSetProjectInfo_String(0, key, "", false)
    old_strings[key] = old
    R.GetSetProjectInfo_String(0, key, value, true)
  end

  R.Main_OnCommand(42230, 0) -- render with these settings, closing the dialog when done

  for key, value in pairs(old_numbers) do R.GetSetProjectInfo(0, key, value, true) end
  for key, value in pairs(old_strings) do R.GetSetProjectInfo_String(0, key, value, true) end
  for i = 0, R.CountTracks(0) - 1 do R.SetTrackSelected(R.GetTrack(0, i), selected[i]) end

  local wanted = {}
  for _, t in ipairs(tracks) do wanted[math.tointeger(R.GetMediaTrackInfo_Value(t, "IP_TRACKNUMBER"))] = name_of(t) end
  local files, mix = {}, nil
  for _, name in ipairs(wav_files(folder)) do
    local number = math.tointeger(tonumber(name:match("^(%d+)%.") or ""))
    if number and wanted[number] then
      -- Named only now: REAPER reads a "/" in a pattern's track name as a folder.
      local named = string.format("%s/%02d %s.wav", folder, number, wanted[number]:gsub("[^%w%- ]", "_"))
      os.rename(folder .. "/" .. name, named)
      files[number] = named
    elseif with_mix then
      mix = folder .. "/mix.wav"
      os.rename(folder .. "/" .. name, mix)
    end
  end
  return files, mix
end

local function is_silent(path)
  if not R.CalculateNormalization then return false end
  local source = R.PCM_Source_CreateFromFile(path)
  local gain = R.CalculateNormalization(source, 2, 0, 0, 0)
  R.PCM_Source_Destroy(source)
  return gain == 0 or gain >= SILENT_GAIN or gain ~= gain
end

-- A printed track from here on: the audio at unity, with what's in the audio gone
-- from the track so it isn't applied twice. Its sends to returns stay.
local function swap_to_audio(track, path)
  for i = R.CountTrackMediaItems(track) - 1, 0, -1 do
    R.DeleteTrackMediaItem(track, R.GetTrackMediaItem(track, i))
  end
  for i = R.TrackFX_GetCount(track) - 1, 0, -1 do R.TrackFX_Delete(track, i) end
  for i = R.GetTrackNumSends(track, -1) - 1, 0, -1 do R.RemoveTrackSend(track, -1, i) end
  for _, name in ipairs(FADER_ENVELOPES) do
    local envelope = R.GetTrackEnvelopeByName(track, name)
    if envelope then R.DeleteEnvelopePointRange(envelope, -1, 1e9) end
  end
  R.SetMediaTrackInfo_Value(track, "D_VOL", 1)
  R.SetMediaTrackInfo_Value(track, "D_PAN", 0)
  R.SetMediaTrackInfo_Value(track, "I_NCHAN", 2)
  R.SetMediaTrackInfo_Value(track, "I_RECARM", 0)
  R.SetMediaTrackInfo_Value(track, "I_RECMON", 0)
  if not path then return end
  local item = R.AddMediaItemToTrack(track)
  local take = R.AddTakeToMediaItem(item)
  local source = R.PCM_Source_CreateFromFile(path)
  R.SetMediaItemTake_Source(take, source)
  R.GetSetMediaItemTakeInfo_String(take, "P_NAME", name_of(track), true)
  R.SetMediaItemInfo_Value(item, "D_POSITION", 0)
  R.SetMediaItemInfo_Value(item, "D_LENGTH", (R.GetMediaSourceLength(source)))
end

-- A bounce that can't finish leaves no tab behind; mix.py removes its files.
local function give_up(message)
  R.Main_SaveProject(0, false)
  R.Main_OnCommand(40860, 0) -- close this tab
  answer({ ok = false, message = message })
end

local function bounce(request)
  local base = find_tab(request.base)
  if base and R.IsProjectDirty(base) == 1 then
    return answer({ ok = false, message = "The master has unsaved changes in REAPER. Save it, then try again." })
  end
  R.OnStopButton()
  R.Main_OnCommand(40859, 0) -- new project tab
  R.Main_openProject("noprompt:" .. request.mix)
  local _, open_file = R.EnumProjects(-1)
  if open_file ~= request.mix then
    return answer({ ok = false, message = "REAPER didn't open " .. request.mix })
  end
  local tracks = {}
  for i = 0, R.CountTracks(0) - 1 do
    local t = R.GetTrack(0, i)
    if role_of(t) == "source" then tracks[#tracks + 1] = t end
  end
  if #tracks == 0 then return give_up("the master has nothing to print") end

  local started = R.time_precise()
  local _, song_end = song_times()
  local files = render(tracks, request.stems, song_end, true)
  local missing, printed, silent = {}, {}, {}
  for _, t in ipairs(tracks) do
    local file = files[math.tointeger(R.GetMediaTrackInfo_Value(t, "IP_TRACKNUMBER"))]
    if not file then missing[#missing + 1] = name_of(t) end
  end
  if #missing > 0 then
    return give_up("REAPER didn't print " .. table.concat(missing, ", "))
  end

  R.Undo_BeginBlock()
  R.PreventUIRefresh(1)
  for _, t in ipairs(tracks) do
    local file = files[math.tointeger(R.GetMediaTrackInfo_Value(t, "IP_TRACKNUMBER"))]
    if is_silent(file) then
      silent[#silent + 1] = name_of(t)
      swap_to_audio(t, nil)
    else
      printed[#printed + 1] = name_of(t)
      swap_to_audio(t, file)
    end
  end
  R.PreventUIRefresh(-1)
  R.UpdateArrange()
  R.Undo_EndBlock("Empire: print to mix session", -1)
  R.Main_SaveProject(0, false)
  answer({ ok = true, mix = request.mix, printed = printed, silent = silent,
    seconds = math.floor(R.time_precise() - started) })
end

local function print_pass(request)
  local here = R.EnumProjects(-1)
  local tab = find_tab(request.mix)
  if tab and R.IsProjectDirty(tab) == 1 then
    return answer({ ok = false, message = "The mix session has unsaved changes in REAPER. Save it, then try again." })
  end
  R.OnStopButton()
  if tab then
    R.SelectProjectInstance(tab)
  else
    R.Main_OnCommand(40859, 0) -- new project tab
    R.Main_openProject("noprompt:" .. request.mix)
    local _, open_file = R.EnumProjects(-1)
    if open_file ~= request.mix then
      return answer({ ok = false, message = "REAPER didn't open " .. request.mix })
    end
    here = nil
  end

  local tracks, roles = {}, {}
  for i = 0, R.CountTracks(0) - 1 do
    local t = R.GetTrack(0, i)
    local role = role_of(t)
    if role then
      tracks[#tracks + 1] = t
      roles[#tracks] = role
    end
  end
  if #tracks == 0 then return answer({ ok = false, message = "the mix session has nothing to print" }) end

  local started = R.time_precise()
  local markers, song_end, bars = song_times()
  local files, mix = render(tracks, request.folder, song_end, true)
  local listed = {}
  for i, t in ipairs(tracks) do
    local file = files[math.tointeger(R.GetMediaTrackInfo_Value(t, "IP_TRACKNUMBER"))]
    if not file then
      return answer({ ok = false, message = "REAPER didn't print " .. name_of(t) })
    end
    listed[#listed + 1] = { name = name_of(t), file = file, role = roles[i], bus_gain_db = bus_gain_db(t) }
  end
  write_json(request.folder .. "/print.json", { schema = "empire.mixprint/v1", session = request.mix,
    master = request.master, markers = markers, song_end = song_end, bars = bars, tracks = listed,
    mix = mix or "" })
  if R.IsProjectDirty(0) == 1 then R.Main_SaveProject(0, false) end -- render settings only; it was clean before
  if here then R.SelectProjectInstance(here) end
  answer({ ok = true, folder = request.folder, tracks = #listed, seconds = math.floor(R.time_precise() - started) })
end

local ok, request = pcall(read_request)
if not ok then
  answer({ ok = false, message = "can't read the request: " .. tostring(request) })
elseif request then
  local done, problem = pcall(request.action == "print" and print_pass or bounce, request)
  if not done then answer({ ok = false, message = "the script failed: " .. tostring(problem) }) end
end
