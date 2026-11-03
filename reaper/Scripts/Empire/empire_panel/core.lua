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

-- Encodes a flat table of strings, which is all the board requests need.
function core.json_object(fields)
  local keys, parts = {}, {}
  for k in pairs(fields) do keys[#keys + 1] = k end
  table.sort(keys)
  for _, k in ipairs(keys) do
    parts[#parts + 1] = encode_string(k) .. ":" .. encode_string(fields[k])
  end
  return "{" .. table.concat(parts, ",") .. "}"
end

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

-- http.sh writes the HTTP status on the first line and the body after it.
function core.parse_reply(text)
  local status, body = text:match("^(%d+)\n(.*)$")
  if not status then return 0, text end
  return tonumber(status), body
end

return core
