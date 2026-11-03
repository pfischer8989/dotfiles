#!/bin/sh
# Creates the panel's board key and adds it to the dashboard, without showing
# it. Run on the REAPER machine. Safe to run again after a failed attempt.
# Usage: setup_key.sh root@<vps>
set -eu
[ $# -eq 1 ] || { echo "usage: $0 root@<vps>" >&2; exit 2; }
file=$HOME/.empire/reaper-panel.env

key=$(sed -n 's/^EMPIRE_PANEL_KEY=//p' "$file" 2>/dev/null | head -n 1)
if [ -z "$key" ]; then
  key=$(openssl rand -hex 32)
  (umask 077; printf 'EMPIRE_PANEL_KEY=%s\n' "$key" > "$file")
fi

printf %s "$key" | ssh "$1" \
  'python3 /opt/empire-dashboard/deploy/add_api_key.py panel && systemctl restart empire-dashboard'
echo "done: key in $file"
