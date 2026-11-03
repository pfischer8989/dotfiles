#!/bin/sh
# Puts a throwaway run on the board for trying the panel, or removes it. Both
# stages are human, so no runner takes them and nothing reaches the vault.
# `options N` writes test chords for pass N, standing in for an agent.
# Usage: test_run.sh create | options N | status | remove | reset
board=${EMPIRE_BOARD_URL:-https://empire.catdevtech.net}
here=$(dirname "$0")
dir=$HOME/.empire/reaper/panel
runs=$HOME/.empire/reaper/runs
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

create_run() {
    call POST /api/tasks '{"id":"panel-test-gate","title":"Panel test: review gate","project":"default","workflow":"Panel Test","run_id":"panel-test","stage":"gate","stage_order":1,"human":true,"reopen":["panel-test-gate"]}'
    call POST /api/tasks '{"id":"panel-test-step","title":"Panel test: plain step","project":"default","workflow":"Panel Test","run_id":"panel-test","stage":"step","stage_order":2,"human":true,"depends_on":["panel-test-gate"]}'
}

remove_run() {
  # only finished tasks can be deleted
  call PATCH /api/tasks/panel-test-step/complete '{"status":"done"}'
  call PATCH /api/tasks/panel-test-gate/complete '{"status":"done"}'
  call DELETE /api/tasks/panel-test-step
  call DELETE /api/tasks/panel-test-gate
  rm -rf "$runs/panel-test"
}

case "$1" in
  create)
    create_run
    python3 "$here/test_options.py" "$runs/panel-test/gate" 1
    ;;
  options)
    python3 "$here/test_options.py" "$runs/panel-test/gate" "$2"
    ;;
  reset)
    remove_run
    create_run
    python3 "$here/test_options.py" "$runs/panel-test/gate" 1
    ;;
  status)
    call GET /api/tasks/panel-test-gate
    call GET /api/tasks/panel-test-step
    ;;
  remove)
    remove_run
    ;;
  *)
    echo "usage: $0 create | options N | status | remove | reset" >&2
    exit 2
    ;;
esac
