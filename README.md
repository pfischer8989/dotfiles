# dotfiles

My personal configuration files for nvim, tmux, ghostty, and AI coding agents. Managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Structure

```
dotfiles/
├── nvim/.config/nvim/
├── herdr-macos/.config/herdr/
├── herdr-linux/.config/herdr/
├── opencode/.config/opencode/    # AGENTS.md, skills/ (every agent skill), agents/ (personalities)
├── claude/.claude/skills/        # links to the skills above, for Claude Code
├── grok/.grok/skills/            # links to the skills above, for Grok
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
stow --no-folding claude grok   # skills for Claude Code and Grok (see below)
stow tmux
stow ghostty
```

The OpenCode package contains user-wide worker defaults (`AGENTS.md`), reusable
skills (`skills/`), and the Empire agent personalities (`agents/` — linus,
rubin, jocko, elon, watts). Hermes (the Empire controller) is Python code in its
own repo (`~/Dropbox/Development/Personal/empire`), not a dotfiles package; its
config and state live in `~/.empire/`.

### Skills

Every agent skill lives once, in `opencode/.config/opencode/skills/<name>/`.
The `claude` and `grok` packages hold only relative links to those folders,
so `stow --no-folding claude grok` makes every skill visible to Claude Code
(`~/.claude/skills/`) and Grok (`~/.grok/skills/`) as well as OpenCode.
`--no-folding` matters: without it, on a host with no `~/.grok` or
`~/.claude` yet, stow would link the whole folder into this repo and the
tool's logins and history would be written here.

To add a skill: create `opencode/.config/opencode/skills/<name>/SKILL.md`, then

```bash
for t in claude/.claude grok/.grok; do
  ln -s ../../../opencode/.config/opencode/skills/<name> $t/skills/<name>
done
stow --no-folding -R claude grok   # on each host after pulling
```

A skill linked into `~/.claude/skills` by hand (the old way) makes stow stop
with "existing target is not owned by stow": move that link aside and stow
again.

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
