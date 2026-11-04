-- Empire Sketch Previous Section
-- Loops the previous region of a sketch and, if playing, jumps to it. Give this a
-- shortcut in the Actions list.

local R = reaper
local HERE = ({ R.get_action_context() })[2]:match("^(.*)[/\\]")
package.path = HERE .. "/empire_panel/?.lua;" .. package.path
local project = require("project")

local regions = project.regions()
if #regions > 0 then
  local start = R.GetSet_LoopTimeRange2(0, false, true, 0, 0, false)
  local current = 1
  for i, region in ipairs(regions) do
    if math.abs(region.start - start) < 0.001 then current = i end
  end
  project.loop_region(regions[(current - 1 + (-1)) % #regions + 1])
end
