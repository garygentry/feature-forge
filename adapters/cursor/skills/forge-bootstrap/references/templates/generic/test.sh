#!/bin/sh
# Behavioral test: run the entrypoint and assert its output.
set -eu

actual="$(./run.sh)"
expected="Hello from {{PROJECT_NAME}}"

if [ "$actual" != "$expected" ]; then
  printf 'FAIL: expected %s but got %s\n' "$expected" "$actual" >&2
  exit 1
fi

printf 'PASS: run.sh produced the expected greeting\n'
