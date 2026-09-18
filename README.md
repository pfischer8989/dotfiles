# dotfiles

My personal configuration files for nvim, tmux, ghostty, and AI coding agents. Managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Structure

```
dotfiles/
├── nvim/.config/nvim/
├── herdr-macos/.config/herdr/
├── herdr-linux/.config/herdr/
├── opencode/.config/opencode/    # AGENTS.md, skills/, agents/ (personalities)
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

stow opencode
stow tmux
stow ghostty
```

The OpenCode package contains user-wide worker defaults (`AGENTS.md`), reusable
skills (`skills/`), and the Empire agent personalities (`agents/` — linus,
rubin, jocko, elon, watts). Hermes (the Empire controller) is Python code in its
own repo (`~/Dropbox/Development/Personal/empire`), not a dotfiles package; its
config and state live in `~/.empire/`.

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
