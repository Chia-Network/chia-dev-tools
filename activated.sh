#!/bin/bash

set -o errexit

SCRIPT_DIRECTORY=$(
  cd -- "$(dirname -- "$0")"
  pwd
)
# shellcheck disable=SC1091
if [ -d "${SCRIPT_DIRECTORY}/venv" ]; then # CI does not use venv
  source "${SCRIPT_DIRECTORY}/venv/bin/activate"
fi
"$@"
