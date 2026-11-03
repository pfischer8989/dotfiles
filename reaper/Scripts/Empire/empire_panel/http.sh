#!/bin/sh
# One board request, run in the background by the Empire panel so REAPER never
# waits on the network. Usage: http.sh METHOD URL OUT [BODY_FILE]
#
# The reply appears at OUT in one step: the HTTP status on the first line (000
# if there was no reply), then the body. The key is passed to curl on stdin, so
# it never shows in the process list.
method=$1
url=$2
out=$3
body=${4:-}
keyfile=${EMPIRE_PANEL_ENV:-$HOME/.empire/reaper-panel.env}
tmp="$out.tmp.$$"
curl=${EMPIRE_PANEL_CURL:-/usr/bin/curl}

finish() {
  { printf '%s\n' "$1"; cat "$tmp.body" 2>/dev/null; } > "$tmp"
  rm -f "$tmp.body"
  mv "$tmp" "$out"
  [ -z "$body" ] || rm -f "$body"
  exit 0
}

key=$(sed -n 's/^\(export \)\{0,1\}EMPIRE_PANEL_KEY=//p' "$keyfile" 2>/dev/null | head -n 1)
if [ -z "$key" ]; then
  printf 'no EMPIRE_PANEL_KEY in %s' "$keyfile" > "$tmp.body"
  finish 000
fi

set -- --config - -sS --max-time 20 -X "$method" -H 'Content-Type: application/json' \
  -o "$tmp.body" -w '%{http_code}'
[ -z "$body" ] || set -- "$@" --data-binary "@$body"

code=$(printf 'header = "Authorization: Bearer %s"\n' "$key" | "$curl" "$@" "$url" 2>"$tmp.err")
if [ $? -ne 0 ] || [ -z "$code" ]; then
  mv "$tmp.err" "$tmp.body"
  finish 000
fi
rm -f "$tmp.err"
finish "$code"
