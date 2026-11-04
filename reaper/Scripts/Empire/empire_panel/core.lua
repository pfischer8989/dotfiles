-- Logic for the Empire panel with no REAPER dependency, so it can be tested
-- with plain Lua: JSON, what's waiting for a person, and the board requests.

local core = {}

-- JSON ----------------------------------------------------------------------

local ESCAPES = { ['"'] = '"', ["\\"] = "\\", ["/"] = "/", b = "\b",
                  f = "\f", n = "\n", r = "\r", t = "\t" }

local function decode_string(s, i)
  local parts, start = {}, i + 1
  local pos = start
  while true do
    local q = s:find('["\\]', pos)
    if not q then error("unterminated string at " .. i) end
    parts[#parts + 1] = s:sub(pos, q - 1)
    if s:sub(q, q) == '"' then return table.concat(parts), q + 1 end
    local c = s:sub(q + 1, q + 1)
    if c == "u" then
      local cp = tonumber(s:sub(q + 2, q + 5), 16)
      if not cp then error("bad \\u escape at " .. q) end
      pos = q + 6
      if cp >= 0xD800 and cp <= 0xDBFF and s:sub(pos, pos + 1) == "\\u" then
        local low = tonumber(s:sub(pos + 2, pos + 5), 16)
        if low and low >= 0xDC00 and low <= 0xDFFF then
          cp = 0x10000 + (cp - 0xD800) * 0x400 + (low - 0xDC00)
          pos = pos + 6
        end
      end
      parts[#parts + 1] = utf8.char(cp)
    else
      local e = ESCAPES[c]
      if not e then error("bad escape at " .. q) end
      parts[#parts + 1] = e
      pos = q + 2
    end
  end
end

local decode_value

local function skip(s, i)
  return s:find("[^ \t\r\n]", i) or #s + 1
end

local function decode_array(s, i)
  local out = {}
  i = skip(s, i + 1)
  if s:sub(i, i) == "]" then return out, i + 1 end
  while true do
    local v
    v, i = decode_value(s, i)
    if v ~= nil then out[#out + 1] = v end -- a null is dropped
    i = skip(s, i)
    local c = s:sub(i, i)
    if c == "]" then return out, i + 1 end
    if c ~= "," then error("expected , or ] at " .. i) end
    i = skip(s, i + 1)
  end
end

local function decode_object(s, i)
  local out = {}
  i = skip(s, i + 1)
  if s:sub(i, i) == "}" then return out, i + 1 end
  while true do
    if s:sub(i, i) ~= '"' then error("expected a key at " .. i) end
    local k, v
    k, i = decode_string(s, i)
    i = skip(s, i)
    if s:sub(i, i) ~= ":" then error("expected : at " .. i) end
    v, i = decode_value(s, skip(s, i + 1))
    out[k] = v
    i = skip(s, i)
    local c = s:sub(i, i)
    if c == "}" then return out, i + 1 end
    if c ~= "," then error("expected , or } at " .. i) end
    i = skip(s, i + 1)
  end
end

decode_value = function(s, i)
  i = skip(s, i)
  local c = s:sub(i, i)
  if c == "{" then return decode_object(s, i) end
  if c == "[" then return decode_array(s, i) end
  if c == '"' then return decode_string(s, i) end
  if s:sub(i, i + 3) == "true" then return true, i + 4 end
  if s:sub(i, i + 4) == "false" then return false, i + 5 end
  if s:sub(i, i + 3) == "null" then return nil, i + 4 end
  local num = s:match("^-?%d+%.?%d*[eE]?[+-]?%d*", i)
  if num and tonumber(num) then return tonumber(num), i + #num end
  error("unexpected input at " .. i)
end

function core.json_decode(s)
  local v, i = decode_value(s, 1)
  if skip(s, i) <= #s then error("trailing data at " .. i) end
  return v
end

local function encode_string(s)
  return '"' .. s:gsub('[%c"\\]', function(c)
    if c == '"' then return '\\"' end
    if c == "\\" then return "\\\\" end
    if c == "\n" then return "\\n" end
    if c == "\r" then return "\\r" end
    if c == "\t" then return "\\t" end
    return string.format("\\u%04x", c:byte())
  end) .. '"'
end

-- Encodes strings, numbers, booleans and tables. A table with a [1] or nothing
-- in it is an array; object keys come out sorted, so the output is stable.
function core.json_encode(v)
  local t = type(v)
  if t == "string" then return encode_string(v) end
  if t == "boolean" then return tostring(v) end
  if t == "number" then
    local i = math.tointeger(v)
    return i and tostring(i) or string.format("%.14g", v)
  end
  if t ~= "table" then error("can't encode a " .. t) end
  local parts = {}
  if v[1] ~= nil or next(v) == nil then
    for _, x in ipairs(v) do parts[#parts + 1] = core.json_encode(x) end
    return "[" .. table.concat(parts, ",") .. "]"
  end
  local keys = {}
  for k in pairs(v) do keys[#keys + 1] = k end
  table.sort(keys)
  for _, k in ipairs(keys) do
    parts[#parts + 1] = encode_string(k) .. ":" .. core.json_encode(v[k])
  end
  return "{" .. table.concat(parts, ",") .. "}"
end

core.json_object = core.json_encode

-- Board ---------------------------------------------------------------------

local function url_encode(s)
  return (s:gsub("[^%w%-_.~]", function(c) return string.format("%%%02X", c:byte()) end))
end

-- The workflows that happen in REAPER; the panel ignores every other run.
-- "Panel Test" is the throwaway run from test_run.sh.
core.REAPER_WORKFLOWS = {
  ["Song Construction"] = true,
  ["Arrangement"] = true,
  ["Mix"] = true,
  ["Master"] = true,
  ["Publish"] = true,
  ["Panel Test"] = true,
}

function core.reaper_runs(runs)
  local out = {}
  for _, run in ipairs(runs or {}) do
    if core.REAPER_WORKFLOWS[run.workflow] then out[#out + 1] = run end
  end
  return out
end

-- A stage is waiting when the dashboard would offer it to a person: the same
-- test as `needs` in the dashboard's index.html.
function core.is_waiting(stage)
  return stage.human == true and stage.status == "ready" and stage.available == true
end

function core.is_review(stage)
  return type(stage.reopen) == "table" and #stage.reopen > 0
end

-- The stages waiting for a person across a /api/workflows response, in order.
function core.waiting(runs)
  local out = {}
  for _, run in ipairs(runs or {}) do
    for _, stage in ipairs(run.stages or {}) do
      if core.is_waiting(stage) then
        out[#out + 1] = { run = run, stage = stage }
      end
    end
  end
  return out
end

-- The request for a decision. Returns method, path, body or nil and a message.
-- As on the dashboard, a review stage has Accept and Another pass (with an
-- optional note for the AI); any other human stage only has Done, which is what
-- "accept" sends for it.
function core.decision(stage, action, note)
  local base = "/api/tasks/" .. url_encode(stage.id)
  note = note or ""
  if action == "accept" then
    if core.is_review(stage) then return "POST", base .. "/accept", nil end
    return "PATCH", base .. "/complete",
      core.json_object({ status = "done", summary = "completed in the REAPER panel" })
  elseif action == "another_pass" then
    if not core.is_review(stage) then return nil, "this stage has no Another pass" end
    return "POST", base .. "/reopen", core.json_object({ note = note })
  end
  return nil, "unknown action " .. tostring(action)
end

-- Options -------------------------------------------------------------------

-- Where a stage's MIDI options for a pass sit on this machine: one
-- <part>-<option>.notes.json per option.
function core.options_dir(root, run_id, stage, round)
  return string.format("%s/%s/%s/pass-%d", root, run_id, stage, round)
end

-- Checks one empire.notes/v1 document. Each note is [start, pitch, channel,
-- length, velocity] in integer ticks at 960 per quarter note, from song start.
-- Returns the document or nil and a message.
function core.check_notes(doc)
  if type(doc) ~= "table" or doc.schema ~= "empire.notes/v1" then
    return nil, "not an empire.notes/v1 file"
  end
  if doc.ppq ~= 960 then return nil, "ppq must be 960" end
  if type(doc.part) ~= "string" or doc.part == "" then return nil, "no part name" end
  if type(doc.notes) ~= "table" or #doc.notes == 0 then return nil, "no notes" end
  for i, n in ipairs(doc.notes) do
    local s, p, c, l, v = n[1], n[2], n[3], n[4], n[5]
    for _, x in ipairs({ s, p, c, l, v }) do
      if math.type(x) ~= "integer" then return nil, "note " .. i .. " is not 5 integers" end
    end
    if #n ~= 5 or s < 0 or p > 127 or p < 0 or c < 0 or c > 15 or l <= 0 or v < 1 or v > 127 then
      return nil, "note " .. i .. " is out of range"
    end
  end
  return doc
end

-- The end of the last note, rounded up to a whole 4/4 bar, in ticks.
function core.notes_end(doc)
  local last = 0
  for _, n in ipairs(doc.notes) do last = math.max(last, n[1] + n[4]) end
  local bar = doc.ppq * 4
  return math.ceil(last / bar) * bar
end

-- Setup ---------------------------------------------------------------------

-- REAPER's key snap root actions (MIDI editor) run in this order from 43500.
core.KEYS = { "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B", "Cb" }
local ROOTS = { 0, 1, 1, 2, 3, 3, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11 }
core.SCALES = { "minor", "major", "harmonic minor", "melodic minor", "dorian", "phrygian",
                "phrygian dominant", "lydian", "mixolydian", "locrian", "minor pentatonic", "major pentatonic" }

function core.index_of(list, value)
  for i, x in ipairs(list) do
    if x == value then return i end
  end
  return nil
end

-- Returns the key snap action for a key and the root REAPER should then report.
function core.key_action(key)
  local i = core.index_of(core.KEYS, key)
  if not i then return nil end
  return 43500 + i - 1, ROOTS[i]
end

function core.setup_file(root, run_id, stage, round)
  return core.options_dir(root, run_id, stage, round) .. "/setup.json"
end

function core.accepted_setup_file(root, run_id, stage)
  return string.format("%s/%s/%s/accepted-setup.json", root, run_id, stage)
end

-- Checks one empire.setup/v1 document. Returns it or nil and a message.
function core.check_setup(doc)
  if type(doc) ~= "table" or doc.schema ~= "empire.setup/v1" then
    return nil, "not an empire.setup/v1 file"
  end
  if type(doc.tempo) ~= "number" or doc.tempo < 20 or doc.tempo > 960 then return nil, "bad tempo" end
  local ts = doc.time_signature
  if type(ts) ~= "table" or math.type(ts[1]) ~= "integer" or ts[1] < 1 or ts[1] > 64
    or not core.index_of({ 1, 2, 4, 8, 16, 32, 64 }, ts[2]) then
    return nil, "bad time signature"
  end
  if not core.index_of(core.KEYS, doc.key) then return nil, "unknown key " .. tostring(doc.key) end
  if not core.index_of(core.SCALES, doc.scale) then return nil, "unknown scale " .. tostring(doc.scale) end
  if type(doc.sections) ~= "table" or #doc.sections == 0 then return nil, "no sections" end
  for i, section in ipairs(doc.sections) do
    if type(section) ~= "table" or type(section.name) ~= "string" or section.name == ""
      or math.type(section.bars) ~= "integer" or section.bars < 1 then
      return nil, "section " .. i .. " needs a name and whole bars"
    end
  end
  if type(doc.tracks) ~= "table" then return nil, "no tracks" end
  for i, track in ipairs(doc.tracks) do
    if type(track) ~= "string" or track == "" then return nil, "track " .. i .. " has no name" end
  end
  return doc
end

-- Each section's first bar (counted from 0), and the bar after the song.
function core.section_bars(doc)
  local starts, bar = {}, 0
  for i, section in ipairs(doc.sections) do
    starts[i] = bar
    bar = bar + section.bars
  end
  return starts, bar
end

function core.setup_summary(doc)
  local _, bars = core.section_bars(doc)
  local bar_qn = doc.time_signature[1] * 4 / doc.time_signature[2]
  local seconds = math.floor(bars * bar_qn * 60 / doc.tempo + 0.5)
  local form = {}
  for i, section in ipairs(doc.sections) do form[i] = section.name .. " " .. section.bars end
  return {
    string.format("Tempo %s   %d/%d   %s %s", core.json_encode(doc.tempo),
      doc.time_signature[1], doc.time_signature[2], doc.key, doc.scale),
    string.format("%s (%d bars, about %d:%02d)", table.concat(form, ", "), bars, seconds // 60, seconds % 60),
    "Tracks: " .. (#doc.tracks > 0 and table.concat(doc.tracks, ", ") or "none"),
  }
end

-- Project notes with the key and scale lines at the top and the rest kept.
function core.notes_with_key(notes, key, scale)
  local kept = {}
  for line in ((notes or "") .. "\n"):gmatch("(.-)\r?\n") do
    if not line:match("^Key: ") and not line:match("^Scale: ") then kept[#kept + 1] = line end
  end
  while kept[#kept] == "" do kept[#kept] = nil end
  table.insert(kept, 1, "Scale: " .. scale)
  table.insert(kept, 1, "Key: " .. key)
  return table.concat(kept, "\n")
end

-- http.sh writes the HTTP status on the first line and the body after it.
function core.parse_reply(text)
  local status, body = text:match("^(%d+)\n(.*)$")
  if not status then return 0, text end
  return tonumber(status), body
end

return core
