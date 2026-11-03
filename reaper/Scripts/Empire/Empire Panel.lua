-- Empire Panel
-- Shows which REAPER runs on the Empire board are waiting for you, with the
-- same Accept and Another pass as the dashboard. The board stays the source of truth; the panel only reads it and
-- sends what the dashboard's buttons send. Board requests run in the background
-- (empire_panel/http.sh), so REAPER never waits on the network.
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
local core = require("core")

local BOARD = os.getenv("EMPIRE_BOARD_URL") or "https://empire.catdevtech.net"
local HOME = os.getenv("HOME")
local DIR = HOME .. "/.empire/reaper/panel"
local LOG = DIR .. "/panel.log"
local HTTP = HERE .. "/empire_panel/http.sh"
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
      decide(item, "accept")
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

  ImGui.SetNextWindowSize(ctx, 420, 520, ImGui.Cond_FirstUseEver)
  local visible, open = ImGui.Begin(ctx, "Empire", true)
  if visible then
    draw_status()
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
