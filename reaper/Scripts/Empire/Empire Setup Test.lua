-- Empire Setup Test
-- Can a script set the MIDI editor's key and scale? Lists the editor's actions
-- for it and tries the settings on a real take over several frames, writing
-- ~/.empire/reaper/setup-test.log. Opens a new project tab; close it without
-- saving.

local R = reaper
local dir = os.getenv("HOME") .. "/.empire/reaper"
local out = {}
local function say(...)
  local parts = {}
  for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
  out[#out + 1] = table.concat(parts, " ")
end
local function save()
  local f = io.open(dir .. "/setup-test.log", "w")
  if f then
    f:write(os.date("%Y-%m-%d %H:%M:%S "), "REAPER ", R.GetAppVersion(), "\n", table.concat(out, "\n"), "\n")
    f:close()
  end
end

-- actions that mention a scale, key snap or root
for _, section in ipairs({ 32060, 0 }) do
  local i = 0
  while true do
    local id, name = R.kbd_enumerateActions(R.SectionFromUniqueID(section), i)
    if not id or id == 0 then break end
    local low = (name or ""):lower()
    if low:find("scale") and not low:find("scale item") or low:find("key snap") or low:find("root") or low:find("key sig") then
      say("action", section, id, name)
    end
    i = i + 1
  end
end
save()

R.Main_OnCommand(40859, 0)
R.InsertTrackAtIndex(0, true)
local item = R.CreateNewMIDIItemInProj(R.GetTrack(0, 0), 0, 4, true)
local take = R.GetActiveTake(item)
R.Main_OnCommand(40297, 0)
R.SetMediaItemSelected(item, true)
R.Main_OnCommand(40153, 0)

local editor = R.MIDIEditor_GetActive()
local function dump(label)
  say(label, "take", R.MIDI_GetScale(take))
  say(label, "editor root", R.MIDIEditor_GetSetting_int(editor, "scale_root"),
      "type", R.MIDIEditor_GetSetting_int(editor, "scale_type"),
      "enabled", R.MIDIEditor_GetSetting_int(editor, "scale_enabled"))
end

local tick = 0
local function step()
  tick = tick + 1
  if tick == 10 then
    dump("before")
    say("set root", R.MIDIEditor_SetSetting_int(editor, "scale_root", 6))
    say("set type", R.MIDIEditor_SetSetting_int(editor, "scale_type", 0x5AD))
  elseif tick == 20 then
    dump("after set")
    local _, chunk = R.GetItemStateChunk(item, "", false)
    say("chunk\n" .. chunk)
    save()
    R.MIDIEditor_OnCommand(editor, 2)
    return
  end
  R.defer(step)
end
R.defer(step)
