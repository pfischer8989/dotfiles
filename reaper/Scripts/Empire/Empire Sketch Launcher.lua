-- Empire Sketch Launcher
-- Clicking a clip in an Empire sketch plays it for that track and section and
-- mutes the other options there. Cmd-click layers. Only acts in a sketch tab,
-- and only when the selection changes. Run it again to stop it.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local project = require("project")

if R.set_action_options then R.set_action_options(1 | 4) end -- rerun stops it; shows as on in the action list

local last = ""

local function selection()
  local parts = {}
  for i = 0, R.CountSelectedMediaItems(0) - 1 do parts[#parts + 1] = tostring(R.GetSelectedMediaItem(0, i)) end
  return table.concat(parts, ",")
end

local function tick()
  local now = selection()
  if now ~= last then
    last = now
    if now ~= "" and project.value("role") == "sketch" then project.launch_selected() end
  end
  R.defer(tick)
end

R.atexit(function()
  if R.set_action_options then R.set_action_options(8) end
end)
R.defer(tick)
