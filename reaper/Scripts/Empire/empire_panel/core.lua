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

function core.check_note_list(notes)
  if type(notes) ~= "table" or #notes == 0 then return nil, "no notes" end
  for i, n in ipairs(notes) do
    local s, p, c, l, v = n[1], n[2], n[3], n[4], n[5]
    for _, x in ipairs({ s, p, c, l, v }) do
      if math.type(x) ~= "integer" then return nil, "note " .. i .. " is not 5 integers" end
    end
    if #n ~= 5 or s < 0 or p > 127 or p < 0 or c < 0 or c > 15 or l <= 0 or v < 1 or v > 127 then
      return nil, "note " .. i .. " is out of range"
    end
  end
  return notes
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
  local checked, err = core.check_note_list(doc.notes)
  if not checked then return nil, err end
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
local SCALE_STEPS = {
  ["minor"] = { 0, 2, 3, 5, 7, 8, 10 }, ["major"] = { 0, 2, 4, 5, 7, 9, 11 },
  ["harmonic minor"] = { 0, 2, 3, 5, 7, 8, 11 }, ["melodic minor"] = { 0, 2, 3, 5, 7, 9, 11 },
  ["dorian"] = { 0, 2, 3, 5, 7, 9, 10 }, ["phrygian"] = { 0, 1, 3, 5, 7, 8, 10 },
  ["phrygian dominant"] = { 0, 1, 4, 5, 7, 8, 10 }, ["lydian"] = { 0, 2, 4, 6, 7, 9, 11 },
  ["mixolydian"] = { 0, 2, 4, 5, 7, 9, 10 }, ["locrian"] = { 0, 1, 3, 5, 6, 8, 10 },
  ["minor pentatonic"] = { 0, 3, 5, 7, 10 }, ["major pentatonic"] = { 0, 2, 4, 7, 9 },
}

-- A scale as MIDI_GetScale reports it: one bit per semitone above the root.
function core.scale_mask(name)
  local steps = SCALE_STEPS[name]
  if not steps then return nil end
  local mask = 0
  for _, step in ipairs(steps) do mask = mask | (1 << step) end
  return mask
end

-- Drum kits. Sketches write drums as General MIDI notes so they don't depend on
-- the kit; the build moves them to the kit's own notes and names those rows.
-- read_master.py holds the same Atlas names. Pitch 36 shows as C2 in the MIDI editor.
core.DRUM_KITS = {
  ["Atlas Kit"] = {
    names = { [36] = "Kick", [37] = "Snare", [38] = "Clap", [39] = "CHat", [40] = "OHat", [41] = "Shaker",
              [42] = "Tom", [43] = "Other", [48] = "Crash", [49] = "Ride", [50] = "Other 2", [51] = "Other 3" },
    from_gm = { [35] = 36, [36] = 36, [37] = 43, [38] = 37, [39] = 38, [40] = 37, [41] = 42, [42] = 39,
                [43] = 42, [44] = 39, [45] = 42, [46] = 40, [47] = 42, [48] = 42, [49] = 48, [50] = 42,
                [51] = 49, [69] = 41, [70] = 41 },
    fallback = 43,
    -- Which track of the template each pad plays on; anything else goes to FX.
    outputs = { order = { "Kick", "Snare", "Clap", "Hats", "Perc 1", "Perc 2", "FX" },
                notes = { [36] = "Kick", [37] = "Snare", [38] = "Clap", [39] = "Hats", [40] = "Hats",
                          [41] = "Perc 1", [42] = "Perc 2", [43] = "Perc 2" }, other = "FX" },
  },
  -- General MIDI names until the kit's own map is known.
  ["Superior Drummer Kit"] = {
    names = { [36] = "Kick", [37] = "Rim", [38] = "Snare", [39] = "Clap", [41] = "Tom Low", [42] = "CHat",
              [43] = "Tom Low 2", [44] = "Pedal Hat", [45] = "Tom Mid", [46] = "OHat", [47] = "Tom Mid 2",
              [48] = "Tom High", [49] = "Crash", [50] = "Tom High 2", [51] = "Ride" },
  },
}

-- The note a General MIDI drum note plays on a template's kit.
function core.drum_note(template, pitch)
  local kit = core.DRUM_KITS[template]
  if not kit or not kit.from_gm then return pitch end
  return kit.from_gm[pitch] or kit.fallback
end

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

-- Sketch --------------------------------------------------------------------

-- Checks one empire.sketch/v1 document: a setup plus clips, each on a section,
-- a part and an option (A, B, C...). Returns it or nil and a message.
function core.check_sketch(doc)
  if type(doc) ~= "table" or doc.schema ~= "empire.sketch/v1" then
    return nil, "not an empire.sketch/v1 file"
  end
  local _, err = core.check_setup(doc.setup)
  if err then return nil, err end
  if doc.ppq ~= 960 then return nil, "ppq must be 960" end
  if math.type(doc.loop_bars) ~= "integer" or doc.loop_bars < 1 then return nil, "bad loop_bars" end
  if math.type(doc.options) ~= "integer" or doc.options < 1 or doc.options > 26 then return nil, "bad options" end
  if type(doc.parts) ~= "table" or #doc.parts == 0 then return nil, "no parts" end
  local sections, parts = {}, {}
  for _, section in ipairs(doc.setup.sections) do sections[section.name] = true end
  for i, part in ipairs(doc.parts) do
    if type(part.name) ~= "string" or part.name == "" then return nil, "part " .. i .. " has no name" end
    parts[part.name] = true
  end
  if type(doc.clips) ~= "table" or #doc.clips == 0 then return nil, "no clips" end
  for i, clip in ipairs(doc.clips) do
    local where = "clip " .. i .. ": "
    if not sections[clip.section] then return nil, where .. "unknown section " .. tostring(clip.section) end
    if not parts[clip.part] then return nil, where .. "unknown part " .. tostring(clip.part) end
    if not core.option_lane(clip.option, doc.options) then return nil, where .. "bad option " .. tostring(clip.option) end
    local _, note_err = core.check_note_list(clip.notes)
    if note_err then return nil, where .. note_err end
  end
  return doc
end

-- The lane (from 0) for option "A", "B"..., or nil.
function core.option_lane(option, options)
  if type(option) ~= "string" or #option ~= 1 then return nil end
  local lane = option:byte() - 65
  if lane < 0 or lane >= options then return nil end
  return lane
end

-- The section (from 1) a sketch bar (from 0) falls in; one loop per section.
function core.sketch_section(bar, loop_bars, count)
  return math.max(1, math.min(count, bar // loop_bars + 1))
end

-- A click launches a clip for its own track and section only. clips: { track,
-- section, selected }. Returns muted by index: false for a selected clip, true
-- for the others in its cell, and nil for every clip in a cell nothing was
-- selected in, which stays as it is.
function core.launch_mutes(clips)
  local function cell(clip) return tostring(clip.track) .. "/" .. clip.section end
  local touched, muted = {}, {}
  for _, clip in ipairs(clips) do
    if clip.selected then touched[cell(clip)] = true end
  end
  for i, clip in ipairs(clips) do
    if touched[cell(clip)] then muted[i] = not clip.selected end
  end
  return muted
end

-- Which fixed lane each picked clip goes on in the master, so that layered
-- picks on one track and section don't overlap. picks: { { track, section } }.
-- Returns lanes by pick and the most lanes each track needs.
function core.master_lanes(picks)
  local used, lanes, needed = {}, {}, {}
  for i, pick in ipairs(picks) do
    local key = tostring(pick.track) .. "/" .. pick.section
    local lane = used[key] or 0
    used[key] = lane + 1
    lanes[i] = lane
    needed[pick.track] = math.max(needed[pick.track] or 0, lane + 1)
  end
  return lanes, needed
end

-- Atlas has no parameter for a pad's output, only a value in its saved state: 16 pads
-- from C2, in order, each with an audio_output_channel counting stereo pairs from 0.
-- REAPER holds that state as base64 lines inside the track's <VST block.
local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local B64_VALUE = {}
for i = 1, 64 do B64_VALUE[B64:byte(i)] = i - 1 end

local function b64_decode(text)
  local out = {}
  for i = 1, #text, 4 do
    local a, b, c, d = text:byte(i, i + 3)
    local n = B64_VALUE[a] << 18 | B64_VALUE[b] << 12 | (B64_VALUE[c] or 0) << 6 | (B64_VALUE[d] or 0)
    local count = c == 61 and 1 or d == 61 and 2 or 3
    out[#out + 1] = string.char(n >> 16, n >> 8 & 255, n & 255):sub(1, count)
  end
  return table.concat(out)
end

local function b64_encode(bytes)
  local out = {}
  for i = 1, #bytes, 3 do
    local a, b, c = bytes:byte(i, i + 2)
    local n = a << 16 | (b or 0) << 8 | (c or 0)
    local function digit(shift) local v = (n >> shift & 63) + 1 return B64:sub(v, v) end
    out[#out + 1] = digit(18) .. digit(12) .. (b and digit(6) or "=") .. (c and digit(0) or "=")
  end
  return table.concat(out)
end

local ATLAS_OUTPUT = "audio_output_channel\0\1\5\1" -- then the value, a 4-byte integer
local ATLAS_PADS = 16

-- Splits a track chunk around a plugin's state: text before, the state's lines, text after.
local function plugin_state(chunk, plugin)
  local _, header_end = chunk:find('<VST [^\n]*' .. plugin .. '[^\n]*\n')
  if not header_end then return nil end
  local close = chunk:find("\n%s*>", header_end)
  if not close then return nil end
  local lines = {}
  for line in chunk:sub(header_end + 1, close - 1):gmatch("[^\n]+") do lines[#lines + 1] = line end
  return chunk:sub(1, header_end), lines, chunk:sub(close)
end

-- A state's bytes and how many are on each line, and back again in the same layout.
local function decode_state(lines)
  local parts, sizes = {}, {}
  for i, line in ipairs(lines) do
    parts[i] = b64_decode(line:match("%S+"))
    sizes[i] = #parts[i]
  end
  return table.concat(parts), sizes
end

local function encode_state(state, sizes, indent)
  local out, at = {}, 1
  for i, size in ipairs(sizes) do
    out[i] = indent .. b64_encode(state:sub(at, at + size - 1))
    at = at + size
  end
  return table.concat(out, "\n")
end

-- The pair each pad plays on, 1 being the main output. Nil if the chunk has no Atlas.
function core.atlas_outputs(chunk)
  local _, lines = plugin_state(chunk, "Atlas")
  if not lines then return nil end
  local state, pairs_out, pos = decode_state(lines), {}, 1
  while #pairs_out < ATLAS_PADS do
    local _, stop = state:find(ATLAS_OUTPUT, pos, true)
    if not stop then return nil end
    pairs_out[#pairs_out + 1] = string.unpack("<i4", state, stop + 1) + 1
    pos = stop + 5
  end
  return pairs_out
end

-- A copy of the chunk with each pad on its template track's output. Those tracks take
-- pairs 2 and up, in outputs.order, leaving the main pair silent. Nil if it can't be done.
function core.route_atlas(chunk, outputs)
  local before, lines, after = plugin_state(chunk, "Atlas")
  if not lines then return nil end
  local pair_of = {}
  for i, name in ipairs(outputs.order) do pair_of[name] = i + 1 end
  local state, sizes = decode_state(lines)
  local pieces, pos = {}, 1
  for pad = 0, ATLAS_PADS - 1 do
    local _, stop = state:find(ATLAS_OUTPUT, pos, true)
    if not stop then return nil end
    local pair = pair_of[outputs.notes[36 + pad] or outputs.other]
    pieces[#pieces + 1] = state:sub(pos, stop) .. string.pack("<i4", pair - 1)
    pos = stop + 5
  end
  pieces[#pieces + 1] = state:sub(pos)
  return before .. encode_state(table.concat(pieces), sizes, lines[1]:match("^%s*")) .. after
end

-- Superior Drummer keeps its mixer as text in its saved state, one block per mic with
-- a "route output N" line, N counting stereo pairs from 0. Mics on a matching rule's
-- track; all other mics go to Room.
local SD_MICS = { { "^Kick", "Kick" }, { "^Snare", "Snare" }, { "^Tom", "Toms" }, { "^Hat", "Hats" },
                  { "^Oh", "OH" }, { "^Ride", "Ride" } }
function core.superior_track(mic)
  for _, rule in ipairs(SD_MICS) do
    if mic:find(rule[1]) then return rule[2] end
  end
  return "Room"
end

local function superior_mixer(state)
  local _, start = state:find("\nmixer {\nlatcomp\n", 1, true)
  local stop = start and state:find("\nbuss 0 {", start, true)
  return start, stop
end

-- Mic name -> the pair it plays on, 1 being the main output. Nil if there's no Superior Drummer.
function core.superior_outputs(chunk)
  local _, lines = plugin_state(chunk, "Superior Drummer")
  if not lines then return nil end
  local state = decode_state(lines)
  local start, stop = superior_mixer(state)
  if not stop then return nil end
  local out = {}
  for mic, value in state:sub(start + 1, stop):gmatch("([^\n{}]+) {\n[^{}]-route output (%-?%d+)") do
    out[mic] = tonumber(value) + 1
  end
  return out
end

-- A copy of the chunk with each mic on its template track's output; those tracks take
-- pairs 2 and up, in order. Nil if it can't be done. The text must stay the same length,
-- because wrappers around it hold its size.
function core.route_superior(chunk, order)
  local before, lines, after = plugin_state(chunk, "Superior Drummer")
  if not lines then return nil end
  local pair_of = {}
  for i, name in ipairs(order) do pair_of[name] = i + 1 end
  local state, sizes = decode_state(lines)
  local start, stop = superior_mixer(state)
  if not stop then return nil end
  local missing = false
  local routed, count = state:sub(start + 1, stop):gsub("([^\n{}]+)( {\n[^{}]-route output )%-?%d+", function(mic, middle)
    local pair = pair_of[core.superior_track(mic)]
    if not pair then missing = true return nil end
    return mic .. middle .. (pair - 1)
  end)
  if count == 0 or missing or #routed ~= stop - start then return nil end
  return before .. encode_state(state:sub(1, start) .. routed .. state:sub(stop + 1), sizes, lines[1]:match("^%s*")) .. after
end

-- http.sh writes the HTTP status on the first line and the body after it.
function core.parse_reply(text)
  local status, body = text:match("^(%d+)\n(.*)$")
  if not status then return 0, text end
  return tonumber(status), body
end

return core
