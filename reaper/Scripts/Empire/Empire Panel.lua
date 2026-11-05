-- Empire Panel
-- Shows which REAPER runs on the Empire board are waiting for you, with the
-- same Accept and Another pass as the dashboard. The board stays the source of truth; the panel only reads it and
-- sends what the dashboard's buttons send. Board requests run in the background
-- (empire_panel/http.sh), so REAPER never waits on the network.
-- It also sets up a project from a stage's setup.json and loads a stage's MIDI.
--
-- Needs ReaImGui (ReaPack: ReaTeam Extensions) and a board key in
-- ~/.empire/reaper-panel.env. Writes timings to ~/.empire/reaper/panel/panel.log.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")

if not R.ImGui_GetBuiltinPath then
  R.ShowMessageBox("Empire Panel needs ReaImGui.\n\nInstall it with Extensions > ReaPack > Browse packages.",
    "Empire Panel", 0)
  return
end

package.path = R.ImGui_GetBuiltinPath() .. "/?.lua;" .. HERE .. "/empire_panel/?.lua;" .. package.path
local ImGui = require("imgui")("0.9")
if R.set_action_options then R.set_action_options(1 | 2) end -- rerunning replaces the old panel: stop it, then start again
local core = require("core")
local project = require("project")

local BOARD = os.getenv("EMPIRE_BOARD_URL") or "https://empire.catdevtech.net"
local HOME = os.getenv("HOME")
local DIR = HOME .. "/.empire/reaper/panel"
local LOG = DIR .. "/panel.log"
local HTTP = HERE .. "/empire_panel/http.sh"
local RUNS = HOME .. "/.empire/reaper/runs"
local RESOURCES = R.GetResourcePath()
local SONG_TEMPLATE = RESOURCES .. "/ProjectTemplates/Empire Song.RPP"
local TRACK_TEMPLATES = RESOURCES .. "/TrackTemplates/Empire"
local KEY_ITEMS = table.concat(core.KEYS, "\0") .. "\0"
local SCALE_ITEMS = table.concat(core.SCALES, "\0") .. "\0"
local POLL_SECONDS = 10
local LOG_SECONDS = 60
local CHECK_SECONDS = 0.1 -- how often to look for a finished request
local STALL_SECONDS = 0.1 -- a frame gap this long would be noticeable

R.RecursiveCreateDirectory(DIR, 0)

local function log(msg)
  local f = io.open(LOG, "a")
  if f then
    f:write(os.date("%Y-%m-%d %H:%M:%S "), msg, "\n")
    f:close()
  end
end

-- Requests ------------------------------------------------------------------

local seq = 0
local inflight = {} -- each: { kind, out, started, on_reply }

local function request(kind, method, path, body, on_reply)
  seq = seq + 1
  local out = string.format("%s/reply-%d-%d", DIR, R.time_precise() * 1000 // 1, seq)
  local cmd = string.format('/bin/sh "%s" %s "%s%s" "%s"', HTTP, method, BOARD, path, out)
  if body then
    local body_file = out .. ".body"
    local f = io.open(body_file, "w")
    if not f then return false end
    f:write(body)
    f:close()
    cmd = cmd .. string.format(' "%s"', body_file)
  end
  local t0 = R.time_precise()
  R.ExecProcess(cmd, -1) -- -1: don't wait
  local spawn = R.time_precise() - t0
  inflight[#inflight + 1] = { kind = kind, out = out, started = t0, on_reply = on_reply, spawn = spawn }
  return true
end

local function has_inflight(kind)
  for _, r in ipairs(inflight) do
    if r.kind == kind then return true end
  end
  return false
end

-- Panel state ---------------------------------------------------------------

local runs, waiting = {}, {}
local board = { ok = false, error = "connecting", at = nil }
local selected_id = nil
local note = ""
local mode = nil -- "accept" while confirming, "another_pass" while writing a note
local focus_note = false
local message = nil
local last_poll = -1e9
local last_check = 0
local stats = { frames = 0, worst = 0, stalls = 0, busy = 0, spawn = 0, http = 0, parse = 0, bytes = 0, polls = 0 }
local last_frame = nil
local last_log = R.time_precise()

local function poll()
  if has_inflight("poll") then return end
  last_poll = R.time_precise()
  request("poll", "GET", "/api/workflows", nil, function(status, text, elapsed)
    stats.http = math.max(stats.http, elapsed)
    stats.polls = stats.polls + 1
    if status ~= 200 then
      board.ok, board.error = false, status == 0 and text or ("HTTP " .. status)
      return
    end
    local t0 = R.time_precise()
    local ok, data = pcall(core.json_decode, text)
    stats.parse = math.max(stats.parse, R.time_precise() - t0)
    stats.bytes = #text
    if not ok or type(data) ~= "table" then
      board.ok, board.error = false, "bad reply: " .. tostring(data)
      return
    end
    runs = core.reaper_runs(data.runs)
    waiting = core.waiting(runs)
    board.ok, board.error, board.at = true, nil, R.time_precise()
  end)
end

local function decide(item, action)
  local method, path, body = core.decision(item.stage, action, note)
  if not method then
    message = path
    return
  end
  local label = ({ accept = "Accepted", another_pass = "Another pass" })[action]
  message = "Sending..."
  log(string.format("%s %s", action, item.stage.id))
  request("decide", method, path, body, function(status, text)
    if status >= 200 and status < 300 then
      message = label .. ": " .. item.stage.id
      log(string.format("%s %s ok", action, item.stage.id))
      note = ""
      last_poll = -1e9 -- show the new state straight away
    else
      message = "Failed (" .. (status == 0 and text or ("HTTP " .. status)) .. ")"
      log(string.format("%s %s failed %s", action, item.stage.id, status))
    end
  end)
end

local function collect_replies()
  local now = R.time_precise()
  if now - last_check < CHECK_SECONDS then return end
  last_check = now
  for i = #inflight, 1, -1 do
    local r = inflight[i]
    local f = io.open(r.out, "r")
    if f then
      local text = f:read("a")
      f:close()
      os.remove(r.out)
      table.remove(inflight, i)
      stats.spawn = math.max(stats.spawn, r.spawn)
      local status, body = core.parse_reply(text)
      r.on_reply(status, body, now - r.started)
    elseif now - r.started > 30 then
      -- http.sh gives up after 20 s, so it never ran or was killed
      table.remove(inflight, i)
      r.on_reply(0, "no reply from http.sh", now - r.started)
    end
  end
end

local function track_frame()
  local now = R.time_precise()
  if last_frame then
    local gap = now - last_frame
    stats.frames = stats.frames + 1
    stats.worst = math.max(stats.worst, gap)
    if gap >= STALL_SECONDS then stats.stalls = stats.stalls + 1 end
  end
  last_frame = now
  if now - last_log >= LOG_SECONDS then
    log(string.format("frames=%d worst_gap=%.0fms stalls=%d busy=%.1fms spawn=%.1fms http=%.0fms parse=%.1fms bytes=%d polls=%d board=%s",
      stats.frames, stats.worst * 1000, stats.stalls, stats.busy * 1000, stats.spawn * 1000, stats.http * 1000,
      stats.parse * 1000, stats.bytes, stats.polls, board.ok and "ok" or tostring(board.error)))
    stats = { frames = 0, worst = 0, stalls = 0, busy = 0, spawn = 0, http = 0, parse = 0, bytes = stats.bytes, polls = 0 }
    last_log = now
  end
end

-- MIDI options --------------------------------------------------------------

local function read_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local text = f:read("a")
  f:close()
  return text
end

-- The option files for a stage's current pass, in name order.
local function option_files(run_id, stage)
  local dir = core.options_dir(RUNS, run_id, stage.stage or stage.id, stage.round or 1)
  local names, i = {}, 0
  R.EnumerateFiles(dir, -1) -- drop REAPER's cached listing
  while true do
    local name = R.EnumerateFiles(dir, i)
    if not name then break end
    if name:match("%.notes%.json$") then names[#names + 1] = name end
    i = i + 1
  end
  table.sort(names)
  return dir, names
end

local function read_options(dir, names)
  local docs = {}
  for _, name in ipairs(names) do
    local ok, doc = pcall(core.json_decode, read_file(dir .. "/" .. name) or "")
    if not ok then return nil, name .. ": " .. tostring(doc) end
    local checked, err = core.check_notes(doc)
    if not checked then return nil, name .. ": " .. err end
    docs[#docs + 1] = doc
  end
  return docs
end

local function find_load(tag)
  for i = 0, R.CountTracks(0) - 1 do
    local track = R.GetTrack(0, i)
    local _, got = R.GetSetMediaTrackInfo_String(track, "P_EXT:empire_load", "", false)
    if got == tag then return track end
  end
  return nil
end

local function insert_option(track, lane, doc)
  local last_qn = core.notes_end(doc) / doc.ppq
  local item = R.CreateNewMIDIItemInProj(track, 0, last_qn, true)
  R.SetMediaItemInfo_Value(item, "I_FIXEDLANE", lane)
  local take = R.GetActiveTake(item)
  for _, n in ipairs(doc.notes) do
    local on = R.MIDI_GetPPQPosFromProjQN(take, n[1] / doc.ppq)
    local off = R.MIDI_GetPPQPosFromProjQN(take, (n[1] + n[4]) / doc.ppq)
    R.MIDI_InsertNote(take, false, false, on, off, n[3], n[2], n[5], true)
  end
  R.MIDI_Sort(take)
end

-- Puts a pass's options on one new track, one fixed lane each, with only the
-- first playing. An earlier pass of the stage stays in the project, muted.
local function load_options(item)
  local stage = item.stage
  local round = stage.round or 1
  local dir, names = option_files(item.run.run_id, stage)
  local docs, err = read_options(dir, names)
  if not docs then
    message = "Can't load: " .. err
    return
  end
  if #docs == 0 then
    message = "No MIDI for this pass yet"
    return
  end
  local base = item.run.run_id .. "/" .. (stage.stage or stage.id) .. "/"
  if find_load(base .. round) then
    message = "This pass is already in the project"
    return
  end

  R.Undo_BeginBlock()
  R.PreventUIRefresh(1)
  for i = 0, R.CountTracks(0) - 1 do
    local track = R.GetTrack(0, i)
    local _, got = R.GetSetMediaTrackInfo_String(track, "P_EXT:empire_load", "", false)
    if got:sub(1, #base) == base then R.SetMediaTrackInfo_Value(track, "B_MUTE", 1) end
  end
  local index = R.CountTracks(0)
  R.InsertTrackAtIndex(index, true)
  local track = R.GetTrack(0, index)
  R.GetSetMediaTrackInfo_String(track, "P_NAME", string.format("%s (pass %d)", docs[1].part, round), true)
  R.GetSetMediaTrackInfo_String(track, "P_EXT:empire_load", base .. round, true)
  R.SetMediaTrackInfo_Value(track, "I_FREEMODE", 2)
  R.SetMediaTrackInfo_Value(track, "I_NUMFIXEDLANES", #docs)
  R.TrackFX_AddByName(track, "ReaSynth", false, -1)
  for i, doc in ipairs(docs) do
    local lane = i - 1
    insert_option(track, lane, doc)
    local label = doc.label and (": " .. doc.label) or ""
    R.GetSetMediaTrackInfo_String(track, "P_LANENAME:" .. lane, string.char(64 + i) .. label, true)
  end
  R.SetMediaTrackInfo_Value(track, "C_LANEPLAYS:0", 1)
  R.PreventUIRefresh(-1)
  R.TrackList_AdjustWindows(false)
  R.UpdateArrange()
  R.Undo_EndBlock("Empire: load " .. docs[1].part .. " pass " .. round, -1)
  message = string.format("Loaded %d options onto '%s (pass %d)'", #docs, docs[1].part, round)
  log(string.format("loaded %s pass %d: %d options", stage.id, round, #docs))
end

-- Project setup -------------------------------------------------------------

local setup_cache = {}

-- The setup file for a stage's current pass, if the agent has written one.
-- Looked up at most every 2 s, because the panel asks on every frame.
local function stage_setup(item)
  local stage = item.stage
  local file = core.setup_file(RUNS, item.run.run_id, stage.stage or stage.id, stage.round or 1)
  local now = R.time_precise()
  if setup_cache.file == file and now - setup_cache.at < 2 then return setup_cache.doc, setup_cache.err end
  local doc, err = nil, nil
  local text = read_file(file)
  if text then
    local ok, decoded = pcall(core.json_decode, text)
    if ok then doc, err = core.check_setup(decoded) else err = tostring(decoded) end
  end
  setup_cache = { file = file, at = now, doc = doc, err = err }
  return doc, err
end

local function setup_tag(item)
  local stage = item.stage
  return item.run.run_id .. "/" .. (stage.stage or stage.id) .. "/" .. (stage.round or 1)
end

local project_value = project.value

-- The key and scale go in the project and the MIDI editor's root.
local function set_key(key, scale)
  local root_ok, scale_ok = project.set_key(key, scale)
  log(string.format("key %s %s, midi root %s, scale %s", key, scale, root_ok and "set" or "not set", scale_ok and "set" or "not set"))
  return root_ok and scale_ok
end

-- Builds the project a setup file describes: Empire Song, tempo, time
-- signature, a marker per section and the tracks through Empire Insert Track.
-- Anything already in this tab stays there, because a used tab gets a new tab.
local function set_up_project(item, doc)
  local tag = setup_tag(item)
  if project_value("setup") == tag then
    message = "This tab is already set up from this pass"
    return
  end
  if not R.file_exists(SONG_TEMPLATE) then
    message = "Can't set up: run Empire Build Templates first"
    return
  end
  for _, name in ipairs(doc.tracks) do
    if not R.file_exists(TRACK_TEMPLATES .. "/" .. name .. ".RTrackTemplate") then
      message = "Can't set up: no track template called " .. name
      return
    end
  end

  if not project.is_empty() then R.Main_OnCommand(40859, 0) end -- new project tab
  R.Main_openProject("template:noprompt:" .. SONG_TEMPLATE)

  R.Undo_BeginBlock()
  project.set_tempo(doc)
  local starts, total = core.section_bars(doc)
  for i, section in ipairs(doc.sections) do
    R.AddProjectMarker2(0, false, R.TimeMap2_beatsToTime(0, 0, starts[i]), 0, section.name, -1, 0)
  end
  R.AddProjectMarker2(0, false, R.TimeMap2_beatsToTime(0, 0, total), 0, "End", -1, 0)
  R.Undo_EndBlock("Empire: tempo, time signature and markers", -1)

  for _, name in ipairs(doc.tracks) do project.insert_template(HERE, name) end

  local root_ok = set_key(doc.key, doc.scale)
  R.SetProjExtState(0, "empire", "setup", tag)
  R.SetEditCurPos(0, true, false)
  R.UpdateTimeline()
  message = root_ok and "Project set up."
    or "Project set up, but the MIDI editor's key didn't change."
  log(string.format("set up %s: %d tracks, %d markers", tag, #doc.tracks, #doc.sections + 1))
end

-- What the project holds now, which is what later stages build on: my changes
-- count, not the proposal.
local function read_project()
  local num, den, tempo = R.TimeMap_GetTimeSigAtTime(0, 0)
  local markers, tracks = {}, {}
  local i = 0
  while true do
    local more, is_region, pos, _, name = R.EnumProjectMarkers3(0, i)
    if more == 0 then break end
    if not is_region then
      local _, bar = R.TimeMap2_timeToBeats(0, pos)
      markers[#markers + 1] = { name = name, bar = bar + 1 }
    end
    i = i + 1
  end
  for t = 0, R.CountTracks(0) - 1 do
    local _, name = R.GetSetMediaTrackInfo_String(R.GetTrack(0, t), "P_NAME", "", false)
    tracks[#tracks + 1] = name
  end
  return { schema = "empire.setup.accepted/v1", tempo = tempo, time_signature = { num, den },
           key = project_value("key"), scale = project_value("scale"), markers = markers, tracks = tracks }
end

-- Saves the project's setup for later stages. A setup stage can only be
-- accepted from its own tab, so that nothing else gets recorded as the song.
local function record_setup(item)
  local prefix = item.run.run_id .. "/" .. (item.stage.stage or item.stage.id) .. "/"
  if project_value("setup"):sub(1, #prefix) ~= prefix then
    message = "Switch to the tab this stage set up, then Accept"
    return false
  end
  local file = core.accepted_setup_file(RUNS, item.run.run_id, item.stage.stage or item.stage.id)
  local tmp = file .. ".tmp"
  local f = io.open(tmp, "w")
  if not f then
    message = "Can't write " .. file
    return false
  end
  f:write(core.json_encode(read_project()), "\n")
  f:close()
  os.rename(tmp, file)
  log("recorded setup " .. file)
  return true
end

-- Interface -----------------------------------------------------------------

local ctx = ImGui.CreateContext("Empire Panel")
local GREEN, RED, AMBER, DIM = 0x8BD17CFF, 0xF7768EFF, 0xE0AF68FF, 0x9AA0A6FF

local function selected_item()
  for _, item in ipairs(waiting) do
    if item.stage.id == selected_id then return item end
  end
  return nil
end

local function draw_status()
  if board.ok then
    ImGui.TextColored(ctx, GREEN, string.format("Board connected, %d s ago", (R.time_precise() - board.at) // 1))
  else
    ImGui.TextColored(ctx, RED, "Board: " .. tostring(board.error))
  end
  if message then ImGui.TextColored(ctx, AMBER, message) end
end

local function draw_project()
  local key, scale = project_value("key"), project_value("scale")
  if key == "" then return end
  ImGui.SeparatorText(ctx, "This project")
  ImGui.SetNextItemWidth(ctx, 70)
  local key_changed, key_index = ImGui.Combo(ctx, "Key", (core.index_of(core.KEYS, key) or 1) - 1, KEY_ITEMS)
  ImGui.SameLine(ctx)
  ImGui.SetNextItemWidth(ctx, 170)
  local scale_changed, scale_index = ImGui.Combo(ctx, "Scale", (core.index_of(core.SCALES, scale) or 1) - 1, SCALE_ITEMS)
  if key_changed or scale_changed then
    set_key(core.KEYS[key_index + 1], core.SCALES[scale_index + 1])
  end
  ImGui.TextColored(ctx, DIM, "REAPER won't let scripts set the scale: pick it in the MIDI editor too.")
end

local function draw_waiting()
  ImGui.SeparatorText(ctx, string.format("Waiting for you (%d)", #waiting))
  if #waiting == 0 then ImGui.TextColored(ctx, DIM, "Nothing right now.") end
  for _, item in ipairs(waiting) do
    local s = item.stage
    local label = string.format("%s: %s (pass %d)##%s", item.run.run_id, s.stage or s.id, s.round or 1, s.id)
    if ImGui.Selectable(ctx, label, s.id == selected_id) and s.id ~= selected_id then
      selected_id, note, mode = s.id, "", nil
    end
  end
end

local function draw_decision()
  local item = selected_item()
  if not item then return end
  local s = item.stage
  ImGui.SeparatorText(ctx, s.title or s.id)
  if s.loop_note then ImGui.TextWrapped(ctx, "Last note: " .. s.loop_note) end

  local setup, setup_err = stage_setup(item)
  if setup_err then ImGui.TextColored(ctx, RED, "Setup file: " .. setup_err) end
  if setup then
    for _, line in ipairs(core.setup_summary(setup)) do ImGui.TextWrapped(ctx, line) end
    if ImGui.Button(ctx, "Set up this project") then set_up_project(item, setup) end
  elseif not setup_err then
    if ImGui.Button(ctx, "Load MIDI into this project") then load_options(item) end
  end

  ImGui.BeginDisabled(ctx, has_inflight("decide"))
  if mode == "another_pass" then
    ImGui.Text(ctx, "What should the AI change?")
    if focus_note then
      ImGui.SetKeyboardFocusHere(ctx)
      focus_note = false
    end
    local _, text = ImGui.InputTextMultiline(ctx, "##note", note, -1, 90)
    note = text
    if ImGui.Button(ctx, "Send") then
      decide(item, "another_pass")
      mode = nil
    end
    ImGui.SameLine(ctx)
    if ImGui.Button(ctx, "Cancel") then mode = nil end
  elseif mode == "accept" then
    local word = core.is_review(s) and "Accept" or "Finish"
    ImGui.TextColored(ctx, AMBER, word .. " " .. (s.stage or s.id) .. "?")
    if ImGui.Button(ctx, "Yes") then
      if not setup or record_setup(item) then decide(item, "accept") end
      mode = nil
    end
    ImGui.SameLine(ctx)
    if ImGui.Button(ctx, "Cancel") then mode = nil end
  else
    if ImGui.Button(ctx, core.is_review(s) and "Accept" or "Done") then mode = "accept" end
    if core.is_review(s) then
      ImGui.SameLine(ctx)
      if ImGui.Button(ctx, "Another pass") then
        mode, focus_note = "another_pass", true
      end
    end
  end
  ImGui.EndDisabled(ctx)
end

local function draw_runs()
  ImGui.SeparatorText(ctx, string.format("Runs (%d)", #runs))
  for _, run in ipairs(runs) do
    local head = string.format("%s%s", run.run_id, run.finished and " (finished)" or "")
    if ImGui.CollapsingHeader(ctx, head) then
      for _, s in ipairs(run.stages or {}) do
        ImGui.Text(ctx, string.format("  %-14s %s", s.stage or s.id, s.status))
      end
    end
  end
end

local function frame()
  local started = R.time_precise()
  track_frame()
  collect_replies()
  if R.time_precise() - last_poll >= POLL_SECONDS then poll() end

  ImGui.SetNextWindowSize(ctx, 460, 560, ImGui.Cond_FirstUseEver)
  local visible, open = ImGui.Begin(ctx, "Empire", true)
  if visible then
    draw_status()
    draw_project()
    draw_waiting()
    draw_decision()
    draw_runs()
    ImGui.End(ctx)
  end
  stats.busy = math.max(stats.busy, R.time_precise() - started)
  if open then
    R.defer(frame)
  else
    log("closed")
  end
end

log("started, REAPER " .. R.GetAppVersion())
R.defer(frame)
