#!/usr/bin/env bash

# shellcheck disable=SC2154,SC2086
# generate long string of args for simulator
create_args="--docker_mode"
if [[ ${mnemonic} != "" ]]; then
  create_args+=" --mnemonic=${mnemonic}"
fi
if [[ ${auto_farm} != "" ]]; then
  create_args+=" --auto-farm=${auto_farm}"
fi
if [[ ${reward_address} != "" ]]; then
  create_args+=" --reward_address=${reward_address}"
fi
if [[ ${fingerprint} != "" ]]; then
  create_args+=" --fingerprint=${fingerprint}"
fi
# create and start simulator
cdv sim create ${create_args}
# start wallet if enabled
if [[ ${start_wallet} == "true" ]]; then
  cdv sim start -w
fi

trap "echo Shutting down ...; cdv sim stop -wd; exit 0" SIGINT SIGTERM

# shellcheck disable=SC2154
# Ensures the log file actually exists, so we can tail successfully
touch "$SIMULATOR_ROOT_PATH/$simulator_name/log/debug.log"
tail -F "$SIMULATOR_ROOT_PATH/$simulator_name/log/debug.log" &

while true; do sleep 1; done
