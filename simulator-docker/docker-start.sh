#!/usr/bin/env bash

# shellcheck disable=SC2154,SC2086
if [[ ${start_wallet} == "true" ]]; then
  start_args="-w"
else
  start_args=""
fi
cdv sim create -d -m ${mnemonic} -a ${auto_farm} -r ${reward_address} -f ${fingerprint}
cdv sim start ${start_args}

trap "echo Shutting down ...; cdv sim stop -wd; exit 0" SIGINT SIGTERM

# shellcheck disable=SC2154
# Ensures the log file actually exists, so we can tail successfully
touch "$SIMULATOR_ROOT_PATH/$simulator_name/log/debug.log"
tail -F "$SIMULATOR_ROOT_PATH/$simulator_name/log/debug.log" &

while true; do sleep 1; done
