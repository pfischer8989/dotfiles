local wezterm = require("wezterm")

local config = wezterm.config_builder()

config.color_scheme = "rose-pine-moon"
config.font = wezterm.font("Hack Nerd Font")
config.font_size = 10.0
config.window_background_opacity = 0.8
config.macos_window_background_blur = 50
config.hide_tab_bar_if_only_one_tab = true
config.window_decorations = "TITLE | RESIZE"

config.window_frame = {
  inactive_titlebar_bg = '#353535',
  active_titlebar_bg = '#2b2042',
  inactive_titlebar_fg = '#cccccc',
  active_titlebar_fg = '#ffffff',
  inactive_titlebar_border_bottom = '#2b2042',
  active_titlebar_border_bottom = '#2b2042',
  button_fg = '#cccccc',
  button_bg = '#2b2042',
  button_hover_fg = '#ffffff',
  button_hover_bg = '#3b3052',
}


-- Copy on mouse selection.
-- Releasing the left mouse button puts the selection straight into the system
-- clipboard (and the primary selection, so middle-click paste keeps working).
-- This matches the upstream default, but being explicit makes the intent clear
-- and protects against a future release changing the default.
config.mouse_bindings = {
  -- Single click / click-drag selection.
  -- CompleteSelectionOrOpenLinkAtMouseCursor copies the selection, but still
  -- opens a link if you click one. Swap it for CompleteSelection(...) below if
  -- you would rather always copy and never open a link.
  {
    event = { Up = { streak = 1, button = "Left" } },
    mods = "NONE",
    action = wezterm.action.CompleteSelectionOrOpenLinkAtMouseCursor("ClipboardAndPrimarySelection"),
  },
  -- Double click selects a word.
  {
    event = { Up = { streak = 2, button = "Left" } },
    mods = "NONE",
    action = wezterm.action.CompleteSelection("ClipboardAndPrimarySelection"),
  },
  -- Triple click selects a line.
  {
    event = { Up = { streak = 3, button = "Left" } },
    mods = "NONE",
    action = wezterm.action.CompleteSelection("ClipboardAndPrimarySelection"),
  },
  -- Middle click pastes. We paste from the system clipboard rather than the
  -- X11 primary selection, so it pastes whatever was last copied with
  -- Ctrl+C / Ctrl+Shift+C anywhere. Shift+middle works even when a TUI has
  -- grabbed the mouse (same trick as Shift+drag to select).
  {
    event = { Down = { streak = 1, button = "Middle" } },
    mods = "NONE",
    action = wezterm.action.PasteFrom("Clipboard"),
  },
  {
    event = { Down = { streak = 1, button = "Middle" } },
    mods = "SHIFT",
    action = wezterm.action.PasteFrom("Clipboard"),
  },
}

-- Dim unfocused windows so the focused one is obvious at a glance.
local UNFOCUSED_FOREGROUND_TEXT_HSB = { hue = 1.0, saturation = 0.25, brightness = 0.45 }
local UNFOCUSED_WINDOW_BACKGROUND_OPACITY = 0.62

-- get_config_overrides() hands back a copy, so the current value is never the
-- same table we last stored; compare the fields instead of the identity.
local function same_text_hsb(actual, expected)
	if actual == nil or expected == nil then
		return actual == expected
	end
	return actual.hue == expected.hue
		and actual.saturation == expected.saturation
		and actual.brightness == expected.brightness
end


return config
