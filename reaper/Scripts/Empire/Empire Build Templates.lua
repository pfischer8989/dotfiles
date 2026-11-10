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
--   Vocal Chain     (vocal tracks: AMEK 9099 -> Presswerk)
--   Verb Short, Verb Long, Shimmer, Delay, Drum Crush   (the returns)
--
-- Instruments you set up inside a plugin (a Komplete Kontrol or Kontakt
-- instrument, a favourite synth patch): save the track's FX chain as
-- FXChains/Empire/Instruments/<Folder>/<Name>.RfxChain and the build makes a
-- track template <Folder>/<Name> from it, with the channel strip after it.
-- A chain saved straight in Instruments/ goes in the Samplers folder.
--
-- Every instrument track has bx_console AMEK 9099, with TB Equalizer Pro last, after
-- any saved chain. Presswerk is only on synth tracks, since the console has a compressor.
--
-- Track templates carry their wiring in P_EXT:empire, read by
-- "Empire Insert Track": folder=, vca=, sends=Name:dB,..., arm=1.
--
-- Templates are saved in category folders under TrackTemplates/Empire/
-- (Drums, Bass, Guitars, Synths, Pads, Drones, Samplers, Audio, FX Bus), which
-- REAPER's own template menu shows as submenus. A template is still known by
-- its name alone ("Atlas Kit", "Synth - Hive"): sketches and setups name it, and
-- Insert Track finds it in whichever folder it is. Names must stay unique.
-- Any template under TrackTemplates/Empire/ that this build didn't make (left
-- by an older build, or one dropped from the list) is moved to Empire-backup/
-- in the resource folder.

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
  VOCALS = rgb(230, 110, 160),
}
-- In track order, with VCA groups 1..9 (VOCALS came last, so the others keep
-- their group numbers). FX comes after them, with no VCA.
local SECTIONS = { "DRUMS", "PERCUSSION", "BASS", "GUITARS", "SYNTHS", "SAMPLES", "SFX", "DRONES", "VOCALS" }

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
  pigments = "VST3:Pigments (Arturia)",
  bazille = "VST3:Bazille (u-he)",
  repro1 = "VST3:Repro-1 (u-he)",
  repro5 = "VST3:Repro-5 (u-he)",
  zebralette3 = "VST3:Zebralette3 (u-he)",
  zebrahz = "VST3:ZebraHZ (u-he)",
  synthmaster2 = { "VST3:SynthMaster 2 (KV331 Audio)", "VST3:SynthMaster2", "AUi:KV331 Audio: SynthMaster 2" },
  kontakt8 = "VST3:Kontakt 8 (Native Instruments)",
  komplete = "VST3:Komplete Kontrol (Native Instruments)",
  midiguitar = "VST3:MIDI Guitar 3 (Jam Origin)",
  engl = "VST3:ENGL Savage 120 (Plugin Alliance)",
  fuchs = "VST3:Fuchs Overdrive Supreme 50 (Plugin Alliance)",
  ampcraft = "VST3:AmpCraft - 1992 (Kazrog)",
  ampbox = "VST3:Ampbox (Mercuriall)",
  tone3000 = "VST3:TONE3000 (TONE3000)",
  supermassive = "VST3:ValhallaSupermassive (Valhalla DSP, LLC)",
  plate = "VST3:Little Plate (Soundtoys)",
  echoboy = "VST3:EchoBoy (Soundtoys)",
  decapitator = "VST3:Decapitator (Soundtoys)",
  crystallizer = "VST3:Crystallizer (Soundtoys)",
  microshift = "VST3:MicroShift (Soundtoys)",
  nam = "VST3:NeuralAmpModeler (Steven Atkinson)",
  eq = "VST3:TB Equalizer Pro (ToneBoosters)",
  punish = "VST3:Punish (Heavyocity)",
  resolve = "VST3:Curves Resolve Stereo (Waves)",
  ad2055 = "VST3:Avalon AD2055 (Kazrog)",
  ad2077 = "VST3:Avalon AD2077 (Kazrog)",
  landr = "VST3:LANDR Mastering Pro (LANDR)",
}

-- A plugin by key; a key can list several names to try (VST3, then AU).
local function addfx(tr, key)
  local names = PLUG[key] or key
  if type(names) == "string" then names = { names } end
  for _, name in ipairs(names) do
    local i = R.TrackFX_AddByName(tr, name, false, -1)
    if i >= 0 then return i end
  end
  say("  ! could not load " .. table.concat(names, " or "))
  return -1
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

local function save_template(folder, name)
  R.RecursiveCreateDirectory(TT .. "/" .. folder, 0)
  R.Main_OnCommand(40297, 0) -- unselect all tracks
  for i = 0, R.CountTracks(0) - 1 do R.SetTrackSelected(R.GetTrack(0, i), true) end
  R.Main_SaveProjectEx(0, TT .. "/" .. folder .. "/" .. name .. ".RTrackTemplate", 1)
  say("track template: " .. folder .. "/" .. name)
end

-- Every template file under TrackTemplates/Empire/, as "Folder/Name" (or
-- "Name" when it's loose in Empire/ itself).
local function template_files()
  local out = {}
  local function scan(folder)
    local dir = folder == "" and TT or TT .. "/" .. folder
    local i = 0
    while true do
      local f = R.EnumerateFiles(dir, i)
      if not f then break end
      local n = f:match("^(.*)%.RTrackTemplate$")
      if n then out[#out + 1] = folder == "" and n or folder .. "/" .. n end
      i = i + 1
    end
  end
  scan("")
  local i = 0
  while true do
    local d = R.EnumerateSubdirectories(TT, i)
    if not d then break end
    scan(d)
    i = i + 1
  end
  return out
end

-- Moves every template this build didn't make out of REAPER's menu, to
-- Empire-backup/, so each template shows once and dropped ones disappear.
local function sweep(built)
  local backup = RES .. "/Empire-backup/TrackTemplates-" .. os.date("%Y%m%d-%H%M%S")
  local moved = 0
  for _, rel in ipairs(template_files()) do
    if not built[rel] then
      local dest = backup .. "/" .. rel .. ".RTrackTemplate"
      R.RecursiveCreateDirectory(dest:match("^(.*)/"), 0)
      local ok, err = os.rename(TT .. "/" .. rel .. ".RTrackTemplate", dest)
      if ok then moved = moved + 1 else say("  ! could not move " .. rel .. ": " .. tostring(err)) end
    end
  end
  if moved > 0 then say("moved " .. moved .. " old templates to " .. backup) end
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

-- A return for the FX folder: 100% wet unless it's your saved chain.
local function fxbus(name, plugs)
  return function()
    local t = track(name, { color = COLOR.FX, ext = "folder=FX" })
    if not chain(t, name, plugs) then full_wet(t) end
  end
end

-- A vocal mic on input 1, armed, through the vocal chain.
local function vocal(name, sends, o)
  o = o or {}
  return function()
    local t = track(name, { color = COLOR.VOCALS, input = true, pan = o.pan,
      ext = "folder=VOCALS;vca=VOCALS;sends=" .. sends .. ";arm=1" })
    chain(t, "Vocal Chain", { "amek", "presswerk" })
    addfx(t, "eq")
    return t
  end
end

-- An instrument from a chain you saved (see the top): the chain, then the strip.
local function saved_instrument(name, file, folder)
  return function()
    local t = track(name, { color = COLOR[folder], midi = true,
      ext = "folder=" .. folder .. ";vca=" .. folder .. ";sends=Verb Long:-20,Delay:-24" })
    if R.TrackFX_AddByName(t, file, false, -1) < 0 then say("  ! could not load chain " .. file) end
    chain(t, "Channel Strip", STRIP)
    addfx(t, "eq")
  end
end

-- Which bus a saved instrument's folder lands on.
local FOLDER_BUS = { Drums = "DRUMS", Bass = "BASS", Guitars = "GUITARS", Synths = "SYNTHS",
  Pads = "SYNTHS", Samplers = "SYNTHS", Drones = "DRONES", Vocals = "VOCALS", Audio = "SAMPLES" }

-- Templates from FXChains/Empire/Instruments/[<Folder>/]<Name>.RfxChain.
local function saved_instruments()
  local out, dir = {}, CH .. "/Instruments"
  local function scan(folder)
    local d = folder == "" and dir or dir .. "/" .. folder
    local i = 0
    while true do
      local f = R.EnumerateFiles(d, i)
      if not f then break end
      local n = f:match("^(.*)%.RfxChain$")
      if n then
        local target = folder == "" and "Samplers" or folder
        out[#out + 1] = { target, n, saved_instrument(n, d .. "/" .. f, FOLDER_BUS[target] or "SYNTHS") }
      end
      i = i + 1
    end
  end
  scan("")
  local i = 0
  while true do
    local sub = R.EnumerateSubdirectories(dir, i)
    if not sub then break end
    scan(sub)
    i = i + 1
  end
  return out
end

-- A reference mix: plays straight to the outputs, past the master chain.
local function reference()
  local t = track("Reference", { color = rgb(120, 120, 120) })
  R.SetMediaTrackInfo_Value(t, "B_MAINSEND", 0)
  R.CreateTrackSend(t, nil) -- hardware output 1/2
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

local LEAD = "Verb Long:-20,Delay:-24"
local PAD = "Verb Long:-14,Shimmer:-20,Delay:-20"
local DRONE = "Verb Long:-12,Shimmer:-18,Delay:-18"
local GTR = "Verb Short:-18,Delay:-22"

-- { folder, template name, builder }. The names are what sketches and setups use.
local TEMPLATES = {
  { "Drums", "Atlas Kit", kit("Atlas Kit", "atlas", core.DRUM_KITS["Atlas Kit"].outputs.order) },
  { "Drums", "Superior Drummer Kit", kit("Superior Drummer Kit", "sd3", { "Kick", "Snare", "Toms", "Hats", "OH", "Room", "Ride" }) },
  { "Drums", "Percussion - Audio", audio("Percussion", "PERCUSSION") },

  { "Bass", "Bass - Zebra 3", synth("Bass", "zebra3", "BASS", "") },
  { "Bass", "Bass - Diva", synth("Bass", "diva", "BASS", "") },
  { "Bass", "Bass - Hive", synth("Bass", "hive", "BASS", "") },
  { "Bass", "Bass - Pigments", synth("Bass", "pigments", "BASS", "") },
  { "Bass", "Bass - Repro-1", synth("Bass", "repro1", "BASS", "") },
  { "Bass", "Bass Guitar - NAM", guitar("Bass Guitar", "nam", "BASS", "") },

  { "Guitars", "Guitar - NAM", guitar("Guitar", "nam", "GUITARS", GTR) },
  { "Guitars", "Guitar Double - NAM", function()
      -- Two performances: record L first (armed), then arm R for the second take.
      guitar("Gtr L", "nam", "GUITARS", "Verb Short:-20", { pan = -0.8 })()
      guitar("Gtr R", "nam", "GUITARS", "Verb Short:-20", { pan = 0.8 })()
      local r = R.GetTrack(0, 1) -- not armed, not monitoring until its take
      R.GetSetMediaTrackInfo_String(r, "P_EXT:empire", "sends=Verb Short:-20", true)
      R.SetMediaTrackInfo_Value(r, "I_RECMON", 0)
    end },
  { "Guitars", "Guitar - ENGL Savage 120", guitar("Guitar", "engl", "GUITARS", GTR) },
  { "Guitars", "Guitar - Fuchs ODS 50", guitar("Guitar", "fuchs", "GUITARS", GTR) },
  { "Guitars", "Guitar - AmpCraft 1992", guitar("Guitar", "ampcraft", "GUITARS", GTR) },
  { "Guitars", "Guitar - Ampbox", guitar("Guitar", "ampbox", "GUITARS", GTR) },
  { "Guitars", "Guitar - TONE3000", guitar("Guitar", "tone3000", "GUITARS", GTR) },
  -- Guitar to MIDI: its own sounds, or the MIDI it sends on to an instrument.
  { "Guitars", "Guitar - MIDI Guitar 3", guitar("MIDI Guitar", "midiguitar", "GUITARS", LEAD) },

  { "Synths", "Synth - Zebra 3", synth("Zebra 3", "zebra3", "SYNTHS", LEAD) },
  { "Synths", "Synth - Diva", synth("Diva", "diva", "SYNTHS", LEAD) },
  { "Synths", "Synth - Hive", synth("Hive", "hive", "SYNTHS", LEAD) },
  { "Synths", "Synth - Pigments", synth("Pigments", "pigments", "SYNTHS", LEAD) },
  { "Synths", "Synth - Bazille", synth("Bazille", "bazille", "SYNTHS", LEAD) },
  { "Synths", "Synth - Repro-1", synth("Repro-1", "repro1", "SYNTHS", LEAD) },
  { "Synths", "Synth - Repro-5", synth("Repro-5", "repro5", "SYNTHS", LEAD) },
  { "Synths", "Synth - Zebralette 3", synth("Zebralette 3", "zebralette3", "SYNTHS", LEAD) },
  { "Synths", "Synth - Zebra HZ", synth("Zebra HZ", "zebrahz", "SYNTHS", LEAD) },
  { "Synths", "Synth - SynthMaster 2", synth("SynthMaster 2", "synthmaster2", "SYNTHS", LEAD) },

  { "Pads", "Pad - Diva", synth("Pad", "diva", "SYNTHS", PAD) },
  { "Pads", "Pad - Zebra 3", synth("Pad", "zebra3", "SYNTHS", PAD) },
  { "Pads", "Pad - Pigments", synth("Pad", "pigments", "SYNTHS", PAD) },
  { "Pads", "Pad - Hive", synth("Pad", "hive", "SYNTHS", PAD) },

  { "Drones", "Drone - Zebra 3", synth("Drone", "zebra3", "DRONES", DRONE) },
  { "Drones", "Drone - Zebra HZ", synth("Drone", "zebrahz", "DRONES", DRONE) },
  { "Drones", "Drone - Pigments", synth("Drone", "pigments", "DRONES", DRONE) },
  { "Drones", "Ambient Guitar - NAM", guitar("Ambient Gtr", "nam", "DRONES", "Shimmer:-10,Verb Long:-12,Delay:-14") },

  -- Empty hosts for any NI library; they land with the synths. Save a loaded
  -- instrument's chain in FXChains/Empire/Instruments/ to get its own template.
  { "Samplers", "Kontakt 8", synth("Kontakt", "kontakt8", "SYNTHS", LEAD) },
  { "Samplers", "Komplete Kontrol", synth("Komplete Kontrol", "komplete", "SYNTHS", LEAD) },

  { "Vocals", "Vocal - Lead", vocal("Lead Vox", "Plate:-16,Verb Long:-20,Delay:-22") },
  { "Vocals", "Vocal - Double", function()
      -- Two takes of the lead, panned; record L first, then arm R.
      vocal("Vox Dbl L", "Plate:-20,Verb Long:-22", { pan = -0.6 })()
      local r = vocal("Vox Dbl R", "Plate:-20,Verb Long:-22", { pan = 0.6 })()
      R.GetSetMediaTrackInfo_String(r, "P_EXT:empire", "sends=Plate:-20,Verb Long:-22", true)
      R.SetMediaTrackInfo_Value(r, "I_RECMON", 0)
    end },
  { "Vocals", "Vocal - Backing", vocal("Backing Vox", "Verb Long:-16,Delay:-20") },

  { "Audio", "Samples - Audio", audio("Samples", "SAMPLES") },
  { "Audio", "SFX - Audio", audio("SFX", "SFX") },
  { "Audio", "Reference", reference },

  -- Returns. Empire Song already has the first five; the rest are extra
  -- colours to insert when a song wants them (send to them by hand).
  { "FX Bus", "Verb Short", fxbus("Verb Short", { "room" }) },
  { "FX Bus", "Verb Long", fxbus("Verb Long", { "vintage" }) },
  { "FX Bus", "Shimmer", fxbus("Shimmer", { "shimmer" }) },
  { "FX Bus", "Delay", fxbus("Delay", { "mfm2" }) },
  { "FX Bus", "Drum Crush", fxbus("Drum Crush", { "presswerk" }) },
  { "FX Bus", "Verb Huge", fxbus("Verb Huge", { "supermassive" }) },
  { "FX Bus", "Plate", fxbus("Plate", { "plate" }) },
  { "FX Bus", "Echo", fxbus("Echo", { "echoboy" }) },
  { "FX Bus", "Parallel Saturation", fxbus("Parallel Saturation", { "decapitator" }) },
  { "FX Bus", "Crystal", fxbus("Crystal", { "crystallizer" }) },
  { "FX Bus", "Wide", fxbus("Wide", { "microshift" }) },
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
for _, t in ipairs(saved_instruments()) do TEMPLATES[#TEMPLATES + 1] = t end
local seen, built = {}, {}
for _, t in ipairs(TEMPLATES) do
  if seen[t[2]] then say("  ! two templates are called " .. t[2] .. "; the later one wins") end
  seen[t[2]] = true
  built[t[1] .. "/" .. t[2]] = true
  clear()
  t[3]()
  save_template(t[1], t[2])
end
sweep(built)
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
