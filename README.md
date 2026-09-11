# dotfiles

My personal configuration files for nvim, tmux, ghostty, and AI coding agents. Managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Structure

```
dotfiles/
├── nvim/.config/nvim/
├── herdr-macos/.config/herdr/
├── herdr-linux/.config/herdr/
├── hermes/.hermes/skills/
├── opencode/.config/opencode/
├── tmux/.tmux.conf
└── ghostty/.config/ghostty/config
```

## Requirements

```bash
brew install stow
```

## Installation

```bash
git clone https://github.com/vossenwout/pookie-dotfiles.git ~/dotfiles
cd ~/dotfiles
stow neovim
# macOS
stow herdr-macos

# Linux
stow herdr-linux

stow hermes
stow opencode
stow tmux
stow ghostty
```

The OpenCode package contains user-wide Empire worker defaults and reusable
skills. The Hermes package contains only the portable Empire controller skill;
Hermes's main `config.yaml`, `.env`, sessions, databases, logs, and bundled
skills remain machine-local. Firstmate is kept as its own checkout because its `AGENTS.md`, private
home state, worktrees, and internal skills are part of its supervisor runtime;
they should not be copied into the global OpenCode configuration. Hermes will
use `~/.local/bin/hermes` and `~/.hermes/` on macOS and Linux, while platform
service files remain separate packages.

This creates symlinks from the expected config locations to the files in this repo.

## Adding a new config

1. Move the config file/folder into the dotfiles repo, mirroring the home directory structure
2. Run `stow <package>` to create the symlink
3. Commit and push

## Keeping in sync

```bash
# pull latest changes
cd ~/dotfiles && git pull

# push changes after editing configs
cd ~/dotfiles && git add . && git commit -m "update" && git push
```
