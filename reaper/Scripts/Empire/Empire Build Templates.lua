-- Empire Build Templates
-- Builds the "Empire Song" project template and the Empire track templates
-- from code. Run it from the Actions list; rerun it after changing the design.
-- It works in a scratch project tab and closes it when done.
--
-- Your own settings win: save an FX chain under FXChains/Empire/ with one of
-- these names and the build uses it instead of the default plugins:
--   Channel Strip   (synth and bass tracks: AMEK 9099 -> Presswerk)
--   Guitar Amp      (guitar tracks: Neural Amp Modeler; no Archetype Plini X
--                    default: its AU crashed REAPER when a build removed it)
--   Bus             (every folder bus but FX: AMEK 9099 -> Presswerk -> Punish -> Curves Resolve)
--   Mix Bus         (master: AMEK 9099 -> Presswerk -> Avalon AD2055 -> AD2077 -> LANDR Mastering Pro)
--   Verb Short, Verb Long, Shimmer, Delay, Drum Crush   (the returns)
--
-- Every instrument track has bx_console AMEK 9099, with TB Equalizer Pro last, after
-- any saved chain. Presswerk is only on synth tracks, since the console has a compressor.
--
-- Track templates carry their wiring in P_EXT:empire, read by
-- "Empire Insert Track": folder=, vca=, sends=Name:dB,..., arm=1.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local core = require("core")
local RES = R.GetResourcePath()
local TT = RES .. "/TrackTemplates/Empire"
local PT = RES .. "/ProjectTemplates"
local CH = RES .. "/FXChains/Empire"

local log = {}
local function say(s)
  log[#log + 1] = s
  R.ShowConsoleMsg(s .. "\n")
end

local function exists(p)
  local f = io.open(p, "r")
  if f then f:close() return true end
  return false
end

local function rgb(r, g, b) return R.ColorToNative(r, g, b) | 0x1000000 end

local COLOR = {
  DRUMS = rgb(214, 84, 64), PERCUSSION = rgb(226, 120, 90), BASS = rgb(170, 90, 150),
  GUITARS = rgb(222, 160, 60), SYNTHS = rgb(80, 140, 220), SAMPLES = rgb(90, 175, 200),
  SFX = rgb(200, 190, 90), DRONES = rgb(110, 190, 165), FX = rgb(150, 110, 200),
}
-- In track order, with VCA groups 1..8. FX comes after them, with no VCA.
local SECTIONS = { "DRUMS", "PERCUSSION", "BASS", "GUITARS", "SYNTHS", "SAMPLES", "SFX", "DRONES" }

local PLUG = {
  amek = "VST3:bx_console AMEK 9099 (Plugin Alliance)",
  presswerk = "VST3:Presswerk (u-he)",
  room = "VST3:ValhallaRoom (Valhalla DSP, LLC)",
  vintage = "VST3:ValhallaVintageVerb (Valhalla DSP, LLC)",
  shimmer = "VST3:ValhallaShimmer (Valhalla DSP, LLC)",
  mfm2 = "VST3:MFM2 (u-he)",
  atlas = "VST3:Atlas (Algonaut)",
  sd3 = "VST3:Superior Drummer 3 (Toontrack)",
  zebra3 = "VST3:Zebra3 (u-he)",
  diva = "VST3:Diva (u-he)",
  hive = "VST3:Hive (u-he)",
  nam = "VST3:NeuralAmpModeler (Steven Atkinson)",
  eq = "VST3:TB Equalizer Pro (ToneBoosters)",
  punish = "VST3:Punish (Heavyocity)",
  resolve = "VST3:Curves Resolve Stereo (Waves)",
  ad2055 = "VST3:Avalon AD2055 (Kazrog)",
  ad2077 = "VST3:Avalon AD2077 (Kazrog)",
  landr = "VST3:LANDR Mastering Pro (LANDR)",
}

local function addfx(tr, key)
  local name = PLUG[key] or key
  local i = R.TrackFX_AddByName(tr, name, false, -1)
  if i < 0 then say("  ! could not load " .. name) end
  return i
end

-- Your saved chain FXChains/Empire/<role>.RfxChain, else the default plugins.
local function chain(tr, role, default)
  local f = CH .. "/" .. role .. ".RfxChain"
  if exists(f) then
    if R.TrackFX_AddByName(tr, f, false, -1) < 0 then say("  ! could not load chain " .. f) end
    return true
  end
  for _, k in ipairs(default) do addfx(tr, k) end
  return false
end

-- Returns are 100% wet: set every Mix / Wet parameter of the chain to full.
local function full_wet(tr)
  for fx = 0, R.TrackFX_GetCount(tr) - 1 do
    for p = 0, R.TrackFX_GetNumParams(tr, fx) - 1 do
      local _, pn = R.TrackFX_GetParamName(tr, fx, p, "")
      local l = pn:lower()
      if l == "mix" or l == "wet" or l == "wetdry" or l == "drywet" or l == "dry/wet" or l == "dry wet" then
        R.TrackFX_SetParamNormalized(tr, fx, p, 1.0)
      end
    end
  end
end

local function track(name, o)
  o = o or {}
  local n = R.CountTracks(0)
  R.InsertTrackAtIndex(n, false)
  local tr = R.GetTrack(0, n)
  R.GetSetMediaTrackInfo_String(tr, "P_NAME", name, true)
  if o.color then R.SetMediaTrackInfo_Value(tr, "I_CUSTOMCOLOR", o.color) end
  if o.depth then R.SetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH", o.depth) end
  if o.nchan then R.SetMediaTrackInfo_Value(tr, "I_NCHAN", o.nchan) end
  if o.pan then R.SetMediaTrackInfo_Value(tr, "D_PAN", o.pan) end
  if o.ext then R.GetSetMediaTrackInfo_String(tr, "P_EXT:empire", o.ext, true) end
  if o.input then
    R.SetMediaTrackInfo_Value(tr, "I_RECINPUT", 0) -- mono, input 1
    R.SetMediaTrackInfo_Value(tr, "I_RECMON", 1)
  end
  if o.midi then
    R.SetMediaTrackInfo_Value(tr, "I_RECINPUT", 4096 | (63 << 5)) -- MIDI, all inputs, all channels
    R.SetMediaTrackInfo_Value(tr, "I_RECMON", 1)
  end
  return tr
end

-- Puts each of Atlas's pads on its own output, so the kit's child tracks get audio.
local function route_atlas(tr, outputs)
  local _, chunk = R.GetTrackStateChunk(tr, "", false)
  local routed = core.route_atlas(chunk, outputs)
  if not routed or not R.SetTrackStateChunk(tr, routed, false) then
    say("  ! could not set Atlas's outputs")
    return
  end
  local _, saved = R.GetTrackStateChunk(tr, "", false)
  local pads = core.atlas_outputs(saved)
  say("  Atlas pad outputs: " .. (pads and table.concat(pads, " ") or "unreadable"))
end

-- Puts each of Superior Drummer's mics on its template track's output.
local function route_superior(tr, order)
  local _, chunk = R.GetTrackStateChunk(tr, "", false)
  local routed = core.route_superior(chunk, order)
  if not routed or not R.SetTrackStateChunk(tr, routed, false) then
    say("  ! could not set Superior Drummer's outputs")
    return
  end
  local _, saved = R.GetTrackStateChunk(tr, "", false)
  local mics = core.superior_outputs(saved)
  say("  Superior Drummer: kick mic on pair " .. tostring(mics and mics["Kick-In"]))
end

-- Multi-out child: receive stereo pair `pair` (1 = outputs 1/2) from inst.
local function receive(inst, child, pair)
  local s = R.CreateTrackSend(inst, child)
  R.SetTrackSendInfo_Value(inst, 0, s, "I_SRCCHAN", (pair - 1) * 2)
  R.SetTrackSendInfo_Value(inst, 0, s, "I_DSTCHAN", 0)
  R.SetTrackSendInfo_Value(inst, 0, s, "I_SENDMODE", 3) -- post-FX, pre-fader
end

local function clear()
  for i = R.CountTracks(0) - 1, 0, -1 do R.DeleteTrack(R.GetTrack(0, i)) end
  for i = R.TrackFX_GetCount(R.GetMasterTrack(0)) - 1, 0, -1 do
    R.TrackFX_Delete(R.GetMasterTrack(0), i)
  end
end

local function save_template(name)
  R.Main_OnCommand(40297, 0) -- unselect all tracks
  for i = 0, R.CountTracks(0) - 1 do R.SetTrackSelected(R.GetTrack(0, i), true) end
  R.Main_SaveProjectEx(0, TT .. "/" .. name .. ".RTrackTemplate", 1)
  say("track template: " .. name)
end

-- ---------------------------------------------------------------- templates

local STRIP = { "amek", "presswerk" }
local BUS = { "amek", "presswerk", "punish", "resolve" }
local MASTER = { "amek", "presswerk", "ad2055", "ad2077", "landr" }

local function synth(name, plug, folder, sends)
  return function()
    local t = track(name, { color = COLOR[folder], midi = true,
      ext = "folder=" .. folder .. ";vca=" .. folder .. ";sends=" .. sends })
    addfx(t, plug)
    chain(t, "Channel Strip", STRIP)
    addfx(t, "eq")
  end
end

-- A track for audio you bring in: loops, samples, effects.
local function audio(name, folder)
  return function()
    local t = track(name, { color = COLOR[folder], ext = "folder=" .. folder .. ";vca=" .. folder })
    addfx(t, "amek")
    addfx(t, "eq")
  end
end

local function guitar(name, amp, folder, sends, o)
  o = o or {}
  return function()
    local t = track(name, { color = COLOR[folder], input = true, pan = o.pan,
      ext = "folder=" .. folder .. ";vca=" .. folder .. ";sends=" .. sends .. ";arm=1" })
    if amp == "nam" then chain(t, "Guitar Amp", { "nam" }) else addfx(t, amp) end
    addfx(t, "amek")
    addfx(t, "eq")
  end
end

local function kit(name, plug, outs)
  return function()
    -- Folder "kit" bus; children receive the instrument's pairs from 3/4 up, and 1/2 is
    -- for anything left on the main output. The plugin's own outputs are set here too.
    track(name, { color = COLOR.DRUMS, depth = 1, ext = "folder=DRUMS;vca=DRUMS" })
    local inst = track(name:gsub(" Kit$", "") .. " (main 1/2)", { color = COLOR.DRUMS, midi = true, nchan = #outs * 2 + 2 })
    addfx(inst, plug)
    if plug == "atlas" then route_atlas(inst, core.DRUM_KITS[name].outputs) end
    if plug == "sd3" then route_superior(inst, outs) end
    R.SetMediaTrackInfo_Value(inst, "C_MAINSEND_NCH", 2) -- only 1/2 to the kit bus
    for i, o in ipairs(outs) do
      local ext = (o == "Kick" or o == "Snare") and "sends=Drum Crush:-12" or nil
      local c = track(o .. " " .. (i + 1) * 2 - 1 .. "/" .. (i + 1) * 2, { color = COLOR.DRUMS, ext = ext })
      receive(inst, c, i + 1)
      addfx(c, "amek")
      addfx(c, "eq")
      if i == #outs then R.SetMediaTrackInfo_Value(c, "I_FOLDERDEPTH", -1) end
    end
  end
end

local TEMPLATES = {
  { "Atlas Kit", kit("Atlas Kit", "atlas", core.DRUM_KITS["Atlas Kit"].outputs.order) },
  { "Superior Drummer Kit", kit("Superior Drummer Kit", "sd3", { "Kick", "Snare", "Toms", "Hats", "OH", "Room", "Ride" }) },
  { "Synth - Zebra 3", synth("Zebra 3", "zebra3", "SYNTHS", "Verb Long:-20,Delay:-24") },
  { "Synth - Diva", synth("Diva", "diva", "SYNTHS", "Verb Long:-20,Delay:-24") },
  { "Synth - Hive", synth("Hive", "hive", "SYNTHS", "Verb Long:-20,Delay:-24") },
  { "Pad - Diva", synth("Pad", "diva", "SYNTHS", "Verb Long:-14,Shimmer:-20,Delay:-20") },
  { "Bass - Zebra 3", synth("Bass", "zebra3", "BASS", "") },
  { "Bass - Diva", synth("Bass", "diva", "BASS", "") },
  { "Bass - Hive", synth("Bass", "hive", "BASS", "") },
  { "Bass Guitar - NAM", guitar("Bass Guitar", "nam", "BASS", "") },
  { "Percussion - Audio", audio("Percussion", "PERCUSSION") },
  { "Samples - Audio", audio("Samples", "SAMPLES") },
  { "SFX - Audio", audio("SFX", "SFX") },
  { "Drone - Zebra 3", synth("Drone", "zebra3", "DRONES", "Verb Long:-12,Shimmer:-18,Delay:-18") },
  { "Guitar - NAM", guitar("Guitar", "nam", "GUITARS", "Verb Short:-18,Delay:-22") },
  { "Guitar Double - NAM", function()
      -- Two performances: record L first (armed), then arm R for the second take.
      guitar("Gtr L", "nam", "GUITARS", "Verb Short:-20", { pan = -0.8 })()
      guitar("Gtr R", "nam", "GUITARS", "Verb Short:-20", { pan = 0.8 })()
      local r = R.GetTrack(0, 1) -- not armed, not monitoring until its take
      R.GetSetMediaTrackInfo_String(r, "P_EXT:empire", "sends=Verb Short:-20", true)
      R.SetMediaTrackInfo_Value(r, "I_RECMON", 0)
    end },
  { "Ambient Guitar - NAM", guitar("Ambient Gtr", "nam", "DRONES", "Shimmer:-10,Verb Long:-12,Delay:-14") },
}

local RETURNS = {
  { "Verb Short", { "room" } },
  { "Verb Long", { "vintage" } },
  { "Shimmer", { "shimmer" } },
  { "Delay", { "mfm2" } },
  { "Drum Crush", { "presswerk" } },
}

local function project()
  for i, s in ipairs(SECTIONS) do
    R.GetSetProjectInfo_String(0, "TRACK_GROUP_NAME:" .. i, s, true)
  end
  -- VCA leads: faders that ride a whole section without touching its bus.
  for i, s in ipairs(SECTIONS) do
    local t = track("VCA " .. s, { color = COLOR[s] })
    R.SetMediaTrackInfo_Value(t, "B_MAINSEND", 0)
    R.SetMediaTrackInfo_Value(t, "I_HEIGHTOVERRIDE", 24)
    R.GetSetTrackGroupMembership(t, "VOLUME_VCA_LEAD", 1 << (i - 1), 1 << (i - 1))
  end
  for _, s in ipairs(SECTIONS) do
    chain(track(s, { color = COLOR[s] }), "Bus", BUS)
  end
  track("FX", { color = COLOR.FX, depth = 1 })
  for i, r in ipairs(RETURNS) do
    local t = track(r[1], { color = COLOR.FX, depth = (i == #RETURNS) and -1 or 0 })
    if not chain(t, r[1], r[2]) then full_wet(t) end
  end
  chain(R.GetMasterTrack(0), "Mix Bus", MASTER)
  R.Main_SaveProjectEx(0, PT .. "/Empire Song.RPP", 0)
  say("project template: Empire Song")
end

-- ---------------------------------------------------------------- main

R.ClearConsole()
R.RecursiveCreateDirectory(TT, 0)
R.RecursiveCreateDirectory(PT, 0)
local previous = R.EnumProjects(-1)
local scratch = RES .. "/Empire-build-tab.RPP"
local tab = io.open(scratch, "w")
tab:write('<REAPER_PROJECT 0.1 "7" 0\n>\n')
tab:close()
R.Main_OnCommand(40859, 0) -- new project tab
R.Main_openProject("noprompt:" .. scratch) -- has a file, so it can close without asking
R.PreventUIRefresh(1)
for _, t in ipairs(TEMPLATES) do
  clear()
  t[2]()
  save_template(t[1])
end
clear()
project()
R.PreventUIRefresh(-1)
R.TrackList_AdjustWindows(false)
R.Main_SaveProject(0, false)
R.Main_OnCommand(40860, 0) -- close the tab
R.SelectProjectInstance(previous)
os.remove(scratch)
say("done.")

local f = io.open(RES .. "/Empire-build.log", "w")
if f then f:write(table.concat(log, "\n"), "\n") f:close() end
