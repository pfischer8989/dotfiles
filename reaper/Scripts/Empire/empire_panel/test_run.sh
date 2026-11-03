#!/bin/sh
# Puts a throwaway run on the board for trying the panel, or removes it. Both
# stages are human, so no runner takes them and nothing reaches the vault.
# Usage: test_run.sh create | status | remove
board=${EMPIRE_BOARD_URL:-https://empire.catdevtech.net}
here=$(dirname "$0")
dir=$HOME/.empire/reaper/panel
mkdir -p "$dir"

call() { # METHOD PATH [JSON]
  out="$dir/test-$$-$(date +%s)-$RANDOM"
  if [ -n "${3:-}" ]; then
    printf '%s' "$3" > "$out.body"
    sh "$here/http.sh" "$1" "$board$2" "$out" "$out.body"
  else
    sh "$here/http.sh" "$1" "$board$2" "$out"
  fi
  cat "$out"
  echo
  rm -f "$out"
}

case "$1" in
  create)
    call POST /api/tasks '{"id":"panel-test-gate","title":"Panel test: review gate","project":"default","workflow":"Panel Test","run_id":"panel-test","stage":"gate","stage_order":1,"human":true,"reopen":["panel-test-gate"]}'
    call POST /api/tasks '{"id":"panel-test-step","title":"Panel test: plain step","project":"default","workflow":"Panel Test","run_id":"panel-test","stage":"step","stage_order":2,"human":true,"depends_on":["panel-test-gate"]}'
    ;;
  status)
    call GET /api/tasks/panel-test-gate
    call GET /api/tasks/panel-test-step
    ;;
  remove)
    call DELETE /api/tasks/panel-test-step
    call DELETE /api/tasks/panel-test-gate
    ;;
  *)
    echo "usage: $0 create | status | remove" >&2
    exit 2
    ;;
esac
