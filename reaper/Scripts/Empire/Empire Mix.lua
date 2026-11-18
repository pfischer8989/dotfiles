-- Empire Mix
-- empire_sketch/mix.py names a job in a request file, and this does it in the open
-- REAPER, answering in a result file instead of showing a message.
--
-- bounce: opens a copy of a master in a new tab and prints each source track, after
-- its plugins and fader. The copy becomes the mix session: those tracks play the
-- audio at unity with no plugins, and buses, returns, sends, VCAs, markers and the
-- master chain stay live. The master isn't touched. If a kit plays everything on its
-- main output and its separate outputs are silent, the kit is printed once per drum
-- by muting the other notes, onto those outputs' tracks. Their plugins and sends were
-- never heard, so they arrive bypassed and muted, to sound like the master.
-- TB Equalizer Pro is for mixing with, so it stays live on the track and out of the
-- print, as it was set.
--
-- print: prints the saved mix session as it stands, tracks and returns, plus the
-- full mix through the master chain, so mix_check.py can measure them.
--
-- fix: opens a copy of a mix session and writes Empire's EQ moves into it (below).

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local core = require("core")

local SKETCHES = os.getenv("HOME") .. "/.empire/reaper/sketches"
local REQUEST, RESULT = SKETCHES .. "/mix-request.json", SKETCHES .. "/mix-result.json"
local TAIL_SECONDS = 5
local MIX_EQ = "TB Equalizer Pro"
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

  local numbers = { RENDER_SETTINGS = with_mix and 1 or 3, RENDER_BOUNDSFLAG = 0, RENDER_STARTPOS = 0,
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
  return gain == 0 or gain == 1 or gain >= SILENT_GAIN or gain ~= gain -- REAPER answers 1 for pure silence
end

local function number_of(track) return math.tointeger(R.GetMediaTrackInfo_Value(track, "IP_TRACKNUMBER")) end

-- The tracks in the kit's folder that take its separate outputs, by output name.
local function kit_children(kit_track, outputs)
  local parent, found = R.GetParentTrack(kit_track), {}
  for i = 0, R.CountTracks(0) - 1 do
    local t = R.GetTrack(0, i)
    if t ~= kit_track and R.GetParentTrack(t) == parent then
      local name = name_of(t)
      for _, output in ipairs(outputs.order) do
        if name == output or name:sub(1, #output + 1) == output .. " " then found[output] = t end
      end
    end
  end
  return found
end

-- Prints a kit once per output, with the other outputs' notes muted. Returns output
-- track -> file. The notes stay changed: the track's MIDI is replaced straight after.
local function split_kit(kit_track, outputs, children, stems)
  local takes = {}
  for i = 0, R.CountTrackMediaItems(kit_track) - 1 do
    local take = R.GetActiveTake(R.GetTrackMediaItem(kit_track, i))
    if take and R.TakeIsMIDI(take) then
      local notes, _, count = {}, R.MIDI_CountEvts(take)
      for n = 0, count - 1 do
        local _, _, muted, _, _, _, pitch = R.MIDI_GetNote(take, n)
        notes[n] = { muted = muted, output = outputs.notes[pitch] or outputs.other }
      end
      takes[#takes + 1] = { take = take, notes = notes }
    end
  end
  local out, temp = {}, stems .. "/split"
  for _, output in ipairs(outputs.order) do
    local played = false
    for _, t in ipairs(takes) do
      for n, note in pairs(t.notes) do
        local plays = note.output == output and not note.muted
        played = played or plays
        R.MIDI_SetNote(t.take, n, nil, not plays, nil, nil, nil, nil, nil, true)
      end
      R.MIDI_Sort(t.take)
    end
    if played and children[output] then
      local files = render({ kit_track }, temp, select(2, song_times()), false)
      local named = string.format("%s/%02d %s.wav", stems, number_of(children[output]), output)
      local file = files[number_of(kit_track)]
      if not file then error("no print of " .. output .. " in " .. temp .. ": " .. table.concat(wav_files(temp), ", ")) end
      os.rename(file, named)
      out[children[output]] = named
    end
  end
  os.remove(temp)
  return out
end

local function add_audio(track, path)
  local item = R.AddMediaItemToTrack(track)
  local take = R.AddTakeToMediaItem(item)
  local source = R.PCM_Source_CreateFromFile(path)
  R.SetMediaItemTake_Source(take, source)
  R.GetSetMediaItemTakeInfo_String(take, "P_NAME", name_of(track), true)
  R.SetMediaItemInfo_Value(item, "D_POSITION", 0)
  R.SetMediaItemInfo_Value(item, "D_LENGTH", (R.GetMediaSourceLength(source)))
end

local function clear_receives(track)
  for i = R.GetTrackNumSends(track, -1) - 1, 0, -1 do R.RemoveTrackSend(track, -1, i) end
end

-- The mix EQ stays out of a print and on the track. Returns each one's enabled state.
local function is_mix_eq(track, fx)
  local _, name = R.TrackFX_GetFXName(track, fx, "")
  return name:find(MIX_EQ, 1, true) ~= nil
end

local function bypass_mix_eq(tracks)
  local was = {}
  for _, track in ipairs(tracks) do
    for fx = 0, R.TrackFX_GetCount(track) - 1 do
      if is_mix_eq(track, fx) then
        was[R.TrackFX_GetFXGUID(track, fx)] = R.TrackFX_GetEnabled(track, fx)
        R.TrackFX_SetEnabled(track, fx, false)
      end
    end
  end
  return was
end

-- A printed track from here on: the audio at unity, with what's in the audio gone
-- from the track so it isn't applied twice. Its sends to returns and mix EQ stay.
local function swap_to_audio(track, path, eq_was)
  for i = R.CountTrackMediaItems(track) - 1, 0, -1 do
    R.DeleteTrackMediaItem(track, R.GetTrackMediaItem(track, i))
  end
  for i = R.TrackFX_GetCount(track) - 1, 0, -1 do
    if is_mix_eq(track, i) then
      R.TrackFX_SetEnabled(track, i, eq_was[R.TrackFX_GetFXGUID(track, i)] ~= false)
    else
      R.TrackFX_Delete(track, i)
    end
  end
  clear_receives(track)
  for _, name in ipairs(FADER_ENVELOPES) do
    local envelope = R.GetTrackEnvelopeByName(track, name)
    if envelope then R.DeleteEnvelopePointRange(envelope, -1, 1e9) end
  end
  R.SetMediaTrackInfo_Value(track, "D_VOL", 1)
  R.SetMediaTrackInfo_Value(track, "D_PAN", 0)
  R.SetMediaTrackInfo_Value(track, "I_NCHAN", 2)
  R.SetMediaTrackInfo_Value(track, "I_RECARM", 0)
  R.SetMediaTrackInfo_Value(track, "I_RECMON", 0)
  if path then add_audio(track, path) end
end

-- An output that was silent in the master now gets a drum, but nothing on it was ever
-- heard: plugins are bypassed and sends muted, for Paul to switch on when he wants them.
local function output_to_audio(track, path)
  clear_receives(track)
  for i = 0, R.TrackFX_GetCount(track) - 1 do R.TrackFX_SetEnabled(track, i, false) end
  for i = 0, R.GetTrackNumSends(track, 0) - 1 do R.SetTrackSendInfo_Value(track, 0, i, "B_MUTE", 1) end
  add_audio(track, path)
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
  local eq_was = bypass_mix_eq(tracks)
  local files = render(tracks, request.stems, song_end, true)
  local missing, silent_track = {}, {}
  for _, t in ipairs(tracks) do
    local file = files[number_of(t)]
    if file then silent_track[t] = is_silent(file) else missing[#missing + 1] = name_of(t) end
  end
  if #missing > 0 then return give_up("REAPER didn't print " .. table.concat(missing, ", ")) end

  local split_files, split_names = {}, {}
  for _, t in ipairs(tracks) do
    local _, kit = R.GetSetMediaTrackInfo_String(t, "P_EXT:empire_drums", "", false)
    local outputs = core.DRUM_KITS[kit] and core.DRUM_KITS[kit].outputs
    if outputs and not silent_track[t] then
      local children, all_silent = kit_children(t, outputs), true
      for _, child in pairs(children) do all_silent = all_silent and silent_track[child] ~= false end
      if next(children) and all_silent then
        split_names[#split_names + 1] = name_of(t)
        for child, file in pairs(split_kit(t, outputs, children, request.stems)) do split_files[child] = file end
        silent_track[t] = true -- its drums are on the outputs now
      end
    end
  end

  local printed, silent = {}, {}
  R.Undo_BeginBlock()
  R.PreventUIRefresh(1)
  for _, t in ipairs(tracks) do
    if split_files[t] then
      printed[#printed + 1] = name_of(t)
      os.remove(files[number_of(t)])
      output_to_audio(t, split_files[t])
    elseif silent_track[t] then
      if not split_files[t] then silent[#silent + 1] = name_of(t) end
      os.remove(files[number_of(t)])
      swap_to_audio(t, nil, eq_was)
    else
      printed[#printed + 1] = name_of(t)
      swap_to_audio(t, files[number_of(t)], eq_was)
    end
  end
  R.PreventUIRefresh(-1)
  R.UpdateArrange()
  R.Undo_EndBlock("Empire: print to mix session", -1)
  R.Main_SaveProject(0, false)
  answer({ ok = true, mix = request.mix, printed = printed, silent = silent, split = split_names,
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
    local parent = R.GetParentTrack(t)
    listed[#listed + 1] = { name = name_of(t), file = file, role = roles[i], bus_gain_db = bus_gain_db(t),
      guid = R.GetTrackGUID(t), parent = parent and name_of(parent) or "", number = number_of(t) }
  end
  write_json(request.folder .. "/print.json", { schema = "empire.mixprint/v1", session = request.mix,
    master = request.master, markers = markers, song_end = song_end, bars = bars, tracks = listed,
    mix = mix or "" })
  if R.IsProjectDirty(0) == 1 then R.Main_SaveProject(0, false) end -- render settings only; it was clean before
  if here then R.SelectProjectInstance(here) end
  answer({ ok = true, folder = request.folder, tracks = #listed, seconds = math.floor(R.time_precise() - started) })
end

-- fix: Empire's EQ moves, in a TB Equalizer Pro of their own on each track ("Empire
-- Fix"), after whatever is on the track. The request holds every move the session
-- should have, so earlier Empire Fix instances and their key sends go first. A
-- ducking band listens to its key tracks, sent to the track's channels 3/4; the
-- track's send to its folder stays on 1/2 so the key isn't heard.

local FIX_FX = "VST3: TB Equalizer Pro (ToneBoosters)"
local FIX_NAME = "TB Equalizer Pro (Empire Fix)"
local FIX_EXT = "P_EXT:empire_fix"
local FIX_TYPES = { bell = 0, lowshelf = 1, highshelf = 2, highpass = 6, lowpass = 7 }

local function is_fix_fx(track, fx)
  local _, renamed = R.TrackFX_GetNamedConfigParm(track, fx, "renamed_name")
  return renamed == FIX_NAME
end

local function fix_state(track)
  local _, s = R.GetSetMediaTrackInfo_String(track, FIX_EXT, "", false)
  local t = {}
  for k, v in s:gmatch("([%w_]+)=([^;]*)") do t[k] = v end
  return t
end

local function clear_fixes()
  local guids = {}
  for i = 0, R.CountTracks(0) - 1 do
    local t = R.GetTrack(0, i)
    guids[R.GetTrackGUID(t)] = t
  end
  for _, track in pairs(guids) do
    for fx = R.TrackFX_GetCount(track) - 1, 0, -1 do
      if is_fix_fx(track, fx) then R.TrackFX_Delete(track, fx) end
    end
    local state = fix_state(track)
    if state.keys then
      local keys = {}
      for g in state.keys:gmatch("[^,]+") do keys[g] = true end
      for i = R.GetTrackNumSends(track, -1) - 1, 0, -1 do
        local source = R.GetTrackSendInfo_Value(track, -1, i, "P_SRCTRACK")
        if source and keys[R.GetTrackGUID(source)] and R.GetTrackSendInfo_Value(track, -1, i, "I_DSTCHAN") == 2 then
          R.RemoveTrackSend(track, -1, i)
        end
      end
      R.SetMediaTrackInfo_Value(track, "I_NCHAN", tonumber(state.nchan) or 2)
      R.SetMediaTrackInfo_Value(track, "C_MAINSEND_NCH", tonumber(state.mainsend) or 0)
    end
    R.GetSetMediaTrackInfo_String(track, FIX_EXT, "", true)
  end
end

-- A track named by GUID, else by number and name, else by a name only it has.
local function find_track(ref)
  local by_name, count = nil, 0
  for i = 0, R.CountTracks(0) - 1 do
    local t = R.GetTrack(0, i)
    if ref.guid and ref.guid ~= "" and R.GetTrackGUID(t) == ref.guid then return t end
    if name_of(t) == ref.name then
      if ref.number and number_of(t) == ref.number then return t end
      by_name, count = t, count + 1
    end
  end
  if count == 1 and not (ref.guid and ref.guid ~= "") then return by_name end
  return nil
end

local function param_names(track, fx)
  local map = {}
  for p = 0, R.TrackFX_GetNumParams(track, fx) - 1 do
    local _, name = R.TrackFX_GetParamName(track, fx, p, "")
    map[(name:lower():gsub("[^%w]", ""))] = p
  end
  return map
end

local function param(map, ...)
  for _, candidate in ipairs({ ... }) do
    if map[candidate] then return map[candidate] end
  end
  local some = {}
  for k in pairs(map) do if #some < 12 then some[#some + 1] = k end end
  error("TB Equalizer Pro has no parameter " .. ({ ... })[1] .. " (it has " .. table.concat(some, ", ") .. ", ...)")
end

local function number_in(text)
  local n, k = (text or ""):match("(%-?[%d%.]+)%s*([kK]?)")
  n = tonumber(n)
  if n and k ~= "" then n = n * 1000 end
  return n
end

local function value_at(track, fx, p, v)
  local ok, text = R.TrackFX_FormatParamValueNormalized(track, fx, p, v, "")
  if ok and text ~= "" then return number_in(text), text end
  R.TrackFX_SetParamNormalized(track, fx, p, v)
  local _, shown = R.TrackFX_GetFormattedParamValue(track, fx, p, "")
  return number_in(shown), shown
end

-- Sets a parameter to the value it shows as `want`, searching its 0..1 range.
local function set_number(track, fx, p, want)
  local low, high = value_at(track, fx, p, 0), value_at(track, fx, p, 1)
  if not low or not high then error("can't read parameter " .. p .. " as a number") end
  local rising, a, b = high > low, 0, 1
  for _ = 1, 40 do
    local mid = (a + b) / 2
    local v = value_at(track, fx, p, mid)
    if v and ((v < want) == rising) then a = mid else b = mid end
  end
  local best, best_off = a, math.huge
  for _, v in ipairs({ a, b }) do
    local shown = value_at(track, fx, p, v)
    if shown and math.abs(shown - want) < best_off then best, best_off = v, math.abs(shown - want) end
  end
  R.TrackFX_SetParamNormalized(track, fx, p, best)
  local _, shown = R.TrackFX_GetFormattedParamValue(track, fx, p, "")
  return shown
end

local function set_text(track, fx, p, want)
  for step = 0, 100 do
    local _, text = value_at(track, fx, p, step / 100)
    if (text or ""):lower():match("^%s*" .. want:lower()) then
      R.TrackFX_SetParamNormalized(track, fx, p, step / 100)
      return text
    end
  end
  error("no setting " .. want .. " for parameter " .. p)
end

local function set_band(track, fx, map, i, band)
  local n = tostring(i)
  local function p(base, unit) return param(map, base .. n .. (unit or ""), base .. n) end
  local shown = { type = band.type }
  R.TrackFX_SetParamNormalized(track, fx, p("visible"), 1)
  R.TrackFX_SetParamNormalized(track, fx, p("enable"), 1)
  set_number(track, fx, p("type"), FIX_TYPES[band.type])
  shown.hz = set_number(track, fx, p("frequency", "hz"), band.hz)
  if band.type == "highpass" or band.type == "lowpass" then
    shown.slope = set_number(track, fx, p("order"), band.slope or 12)
  else
    shown.db = set_number(track, fx, p("gain", "db"), band.db or 0)
    shown.q = set_number(track, fx, p("q"), band.q or (band.type == "bell" and 1 or 0.707))
  end
  local duck = band.duck
  if duck then
    R.TrackFX_SetParamNormalized(track, fx, p("bypassdynamics"), 0)
    shown.duck_db = set_number(track, fx, p("range", "db"), duck.db)
    shown.threshold_db = set_number(track, fx, p("thresha", "db"), duck.threshold_db)
    shown.attack_ms = set_number(track, fx, p("time", "ms"), duck.attack_ms or 10)
    shown.release_ms = set_number(track, fx, p("release", "ms"), duck.release_ms or 150)
  else
    set_number(track, fx, p("range", "db"), 0)
    R.TrackFX_SetParamNormalized(track, fx, p("bypassdynamics"), 1)
  end
  return shown
end

local function add_keys(track, fx, keys)
  local guids, state = {}, { nchan = R.GetMediaTrackInfo_Value(track, "I_NCHAN"),
    mainsend = R.GetMediaTrackInfo_Value(track, "C_MAINSEND_NCH") }
  if state.nchan < 4 then R.SetMediaTrackInfo_Value(track, "I_NCHAN", 4) end
  R.SetMediaTrackInfo_Value(track, "C_MAINSEND_NCH", 2)
  for _, key in ipairs(keys) do
    local s = R.CreateTrackSend(key, track)
    R.SetTrackSendInfo_Value(key, 0, s, "I_SRCCHAN", 0)
    R.SetTrackSendInfo_Value(key, 0, s, "I_DSTCHAN", 2)
    R.SetTrackSendInfo_Value(key, 0, s, "D_VOL", 1)
    R.SetTrackSendInfo_Value(key, 0, s, "I_SENDMODE", 0)
    guids[#guids + 1] = R.GetTrackGUID(key)
  end
  R.GetSetMediaTrackInfo_String(track, FIX_EXT, string.format("keys=%s;nchan=%d;mainsend=%d",
    table.concat(guids, ","), math.floor(state.nchan), math.floor(state.mainsend)), true)
  return { track = track, fx = fx }
end

-- The plugin's inputs as they're laid out now: they change once it has taken its Ext
-- input and been loaded again (four main inputs and SideChain 1-4 before, Input L/R
-- and SideChain L/R after). Returns the input count and the sidechain pins.
local function layout(w)
  local _, pins = R.TrackFX_GetIOSize(w.track, w.fx)
  local side = {}
  for pin = 0, (pins or 0) - 1 do
    local _, name = R.TrackFX_GetNamedConfigParm(w.track, w.fx, "in_pin_" .. pin)
    if (name or ""):lower():match("^side%s*chain") then side[#side + 1] = pin end
  end
  return pins or 0, side
end

-- The pins are set once the plugin has taken its Ext input: switching it makes REAPER
-- lay the sidechain pins out again a moment later, over anything set before.
local function wanted_bits(pin, side)
  if pin == side[1] then return 1 << 2 elseif pin == side[2] then return 1 << 3 end
  if pin == 0 or pin == 1 then return 1 << pin end
  return 0
end

local function wire(w)
  local pins, side = layout(w)
  for pin = 0, pins - 1 do R.TrackFX_SetPinMappings(w.track, w.fx, 0, pin, wanted_bits(pin, side), 0) end
end

local function wired(w)
  local pins, side = layout(w)
  if #side < 2 then return false end
  for pin = 0, pins - 1 do
    if R.TrackFX_GetPinMappings(w.track, w.fx, 0, pin) ~= wanted_bits(pin, side) then return false end
  end
  return true
end

local SETTLE_SECONDS, CHECKS = 1.0, 4

-- Waits, wires, waits again and checks, a few times, then saves and answers.
local function wire_then(wiring, done)
  local round, at = 0, R.time_precise()
  local function step()
    if R.time_precise() - at < SETTLE_SECONDS then return R.defer(step) end
    local all = true
    for _, w in ipairs(wiring) do all = all and wired(w) end
    if all and round > 0 then return done(true) end
    round = round + 1
    if round > CHECKS then return done(false) end
    for _, w in ipairs(wiring) do
      if round == 1 then -- load it again, so it opens its sidechain with Ext already set
        R.TrackFX_SetOffline(w.track, w.fx, true)
        R.TrackFX_SetOffline(w.track, w.fx, false)
      end
      wire(w)
    end
    at = R.time_precise()
    R.defer(step)
  end
  step()
end

local function fix(request)
  local base = find_tab(request.base)
  if base and R.IsProjectDirty(base) == 1 then
    return answer({ ok = false, message = "The mix session has unsaved changes in REAPER. Save it, then try again." })
  end
  R.OnStopButton()
  if base and request.close_base then
    R.SelectProjectInstance(base)
    R.Main_OnCommand(40860, 0) -- close that tab: it's the last fix, and this one replaces it
  end
  R.Main_OnCommand(40859, 0) -- new project tab
  R.Main_openProject("noprompt:" .. request.mix)
  local _, open_file = R.EnumProjects(-1)
  if open_file ~= request.mix then
    return answer({ ok = false, message = "REAPER didn't open " .. request.mix })
  end

  local targets = {}
  for _, entry in ipairs(request.tracks) do
    local track = find_track(entry)
    if not track then return give_up("no track " .. entry.name .. " in the mix session") end
    local keys = {}
    for _, ref in ipairs(entry.keys or {}) do
      local key = find_track(ref)
      if not key then return give_up("no key track " .. ref.name .. " in the mix session") end
      keys[#keys + 1] = key
    end
    targets[#targets + 1] = { entry = entry, track = track, keys = keys }
  end

  R.Undo_BeginBlock()
  R.PreventUIRefresh(1)
  clear_fixes()
  local applied, wiring = {}, {}
  for _, t in ipairs(targets) do
    local fx = R.TrackFX_AddByName(t.track, FIX_FX, false, -1)
    if fx < 0 then error("couldn't add " .. FIX_FX .. " to " .. t.entry.name) end
    R.TrackFX_SetNamedConfigParm(t.track, fx, "renamed_name", FIX_NAME)
    local map, bands = param_names(t.track, fx), {}
    for i, band in ipairs(t.entry.bands) do bands[i] = set_band(t.track, fx, map, i, band) end
    if #t.keys > 0 then
      set_text(t.track, fx, param(map, "inputbus"), "Ext")
      wiring[#wiring + 1] = add_keys(t.track, fx, t.keys)
    end
    applied[#applied + 1] = { name = t.entry.name, bands = bands }
  end
  R.PreventUIRefresh(-1)
  R.UpdateArrange()
  R.Undo_EndBlock("Empire: fix the mix", -1)
  local tab = R.EnumProjects(-1)
  wire_then(wiring, function(ok)
    local ok_save = pcall(function()
      R.SelectProjectInstance(tab)
      R.Main_SaveProject(tab, false)
    end)
    if not ok then
      local seen = {}
      for _, w in ipairs(wiring) do
        local pins = {}
        for pin = 0, (layout(w)) - 1 do
          local _, pin_name = R.TrackFX_GetNamedConfigParm(w.track, w.fx, "in_pin_" .. pin)
          pins[#pins + 1] = pin_name .. "=" .. R.TrackFX_GetPinMappings(w.track, w.fx, 0, pin)
        end
        seen[#seen + 1] = name_of(w.track) .. " " .. table.concat(pins, " ")
      end
      return answer({ ok = false, message = "the sidechain pins of TB Equalizer Pro wouldn't stay on channels 3/4 ("
        .. table.concat(seen, "; ") .. ")" })
    end
    answer({ ok = ok_save, fixed = request.mix, applied = applied, message = ok_save and nil or "couldn't save" })
  end)
end

local ACTIONS = { print = print_pass, fix = fix, bounce = bounce }

local ok, request = pcall(read_request)
if not ok then
  answer({ ok = false, message = "can't read the request: " .. tostring(request) })
elseif request then
  local done, problem = pcall(ACTIONS[request.action] or bounce, request)
  if not done then
    local message = "the script failed: " .. tostring(problem)
    local _, open_file = R.EnumProjects(-1)
    if request.action ~= "print" and open_file == request.mix then give_up(message) else answer({ ok = false, message = message }) end
  end
end
