-- lua5.4 empire_panel/test_core.lua (from reaper/Scripts/Empire)
package.path = "empire_panel/?.lua;" .. package.path
local core = require("core")

local failed = 0
local function check(name, got, want)
  if got ~= want then
    failed = failed + 1
    print("FAIL " .. name .. ": got " .. tostring(got) .. ", want " .. tostring(want))
  end
end

-- JSON
local v = core.json_decode('{"a": [1, -2.5, 1e3, true, false, null, "x"], "b": {"c": "d"}, "e": null}')
check("array length drops null", #v.a, 6)
check("negative float", v.a[2], -2.5)
check("exponent", v.a[3], 1000)
check("true", v.a[4], true)
check("false", v.a[5], false)
check("nested", v.b.c, "d")
check("null key", v.e, nil)
check("escapes", core.json_decode([["a\"b\\c\n\t\/"]]), 'a"b\\c\n\t/')
check("unicode", core.json_decode([["café"]]), "café")
check("surrogate pair", core.json_decode([["🎸"]]), "🎸")
check("empty array", #core.json_decode("[ ]"), 0)
check("empty object", next(core.json_decode("{ }")), nil)
check("long string", #core.json_decode('"' .. string.rep("x", 100000) .. '"'), 100000)
for _, bad in ipairs({ "{", "[1,", '"x', "{1:2}", "nope", "[1] 2" }) do
  check("rejects " .. bad, (pcall(core.json_decode, bad)), false)
end

-- encoding round-trips through the decoder
local note = 'line "one"\nback\\slash\ttab\1 é'
local enc = core.json_object({ note = note, b = "x" })
check("key order is stable", enc:sub(1, 5), '{"b":')
check("round trip", core.json_decode(enc).note, note)

-- waiting
local runs = core.json_decode([[{"runs": [
  {"run_id": "r1", "stages": [
    {"id": "agent", "human": false, "status": "ready", "available": true},
    {"id": "later", "human": true, "status": "ready", "available": false},
    {"id": "gone", "human": true, "status": "done", "available": true},
    {"id": "gate", "human": true, "status": "ready", "available": true, "reopen": ["a", "gate"]}
  ]},
  {"run_id": "r2", "stages": [
    {"id": "step", "human": true, "status": "ready", "available": true, "reopen": null}
  ]}
]}]]).runs
local w = core.waiting(runs)
check("waiting count", #w, 2)
check("waiting first", w[1].stage.id, "gate")
check("waiting run", w[1].run.run_id, "r1")
check("waiting second", w[2].stage.id, "step")
check("no runs", #core.waiting(nil), 0)

-- only REAPER workflows
local mixed = {
  { run_id = "song", workflow = "Song Construction" },
  { run_id = "cover", workflow = "Cover Art" },
  { run_id = "none" },
  { run_id = "mix", workflow = "Mix" },
}
local kept = core.reaper_runs(mixed)
check("keeps REAPER runs", #kept, 2)
check("keeps first", kept[1].run_id, "song")
check("keeps second", kept[2].run_id, "mix")
check("no runs to filter", #core.reaper_runs(nil), 0)

-- decisions
local gate, step = w[1].stage, w[2].stage
local m, p, b = core.decision(gate, "accept")
check("accept method", m, "POST"); check("accept path", p, "/api/tasks/gate/accept"); check("accept body", b, nil)
m, p, b = core.decision(step, "accept")
check("done method", m, "PATCH"); check("done path", p, "/api/tasks/step/complete")
check("done status", core.json_decode(b).status, "done")
m, p, b = core.decision(gate, "another_pass", "slower")
check("pass path", p, "/api/tasks/gate/reopen"); check("pass note", core.json_decode(b).note, "slower")
m, p, b = core.decision(gate, "another_pass")
check("note is optional", core.json_decode(b).note, "")
m, p = core.decision(step, "another_pass", "x")
check("no pass without a loop", m, nil)
check("no comment action", (core.decision(gate, "comment", "x")), nil)
_, p = core.decision({ id = "a b/c" }, "accept")
check("id is url-encoded", p, "/api/tasks/a%20b%2Fc/complete")
check("unknown action", (core.decision(gate, "explode")), nil)

-- options
check("options dir", core.options_dir("/r", "run", "gate", 2), "/r/run/gate/pass-2")
local good = { schema = "empire.notes/v1", ppq = 960, part = "chords",
               notes = { { 0, 60, 0, 960, 100 }, { 3840, 64, 0, 480, 90 } } }
check("good notes", core.check_notes(good), good)
check("rounds up to a bar", core.notes_end(good), 7680)
good.notes[2] = { 3360, 64, 0, 480, 90 }
check("exact bar", core.notes_end(good), 3840)
local function bad_notes(change)
  local doc = { schema = "empire.notes/v1", ppq = 960, part = "chords", notes = { { 0, 60, 0, 960, 100 } } }
  change(doc)
  return (core.check_notes(doc))
end
check("wrong schema", bad_notes(function(d) d.schema = "x" end), nil)
check("wrong ppq", bad_notes(function(d) d.ppq = 480 end), nil)
check("no part", bad_notes(function(d) d.part = nil end), nil)
check("no notes", bad_notes(function(d) d.notes = {} end), nil)
check("float tick", bad_notes(function(d) d.notes[1][1] = 0.5 end), nil)
check("pitch range", bad_notes(function(d) d.notes[1][2] = 128 end), nil)
check("zero length", bad_notes(function(d) d.notes[1][4] = 0 end), nil)
check("short note", bad_notes(function(d) d.notes[1] = { 0, 60, 0 } end), nil)
check("not a table", (core.check_notes("x")), nil)

-- replies
local status, body = core.parse_reply('200\n{"ok":\ntrue}')
check("reply status", status, 200); check("reply body", body, '{"ok":\ntrue}')
status, body = core.parse_reply("000\ncurl: failed")
check("no reply", status, 0); check("no reply text", body, "curl: failed")
status = core.parse_reply("garbage")
check("garbage reply", status, 0)

if failed > 0 then print(failed .. " failed"); os.exit(1) end
print("ok")
