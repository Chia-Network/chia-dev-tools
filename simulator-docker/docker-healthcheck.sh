#!/bin/bash

# shellcheck disable=SC2154
if [[ ${healthcheck} != "true" ]]; then
    exit 0
fi

dt () {
    date +%FT%T.%3N
}

logger () {
    # shellcheck disable=SC2154
    echo "$1" >> "${SIMULATOR_ROOT_PATH}/${simulator_name}/log/debug.log"
}

# Node always runs in simulation mode & the wallet is run by the start wallet arg

# node check
  curl -X POST --fail \
    --cert "${SIMULATOR_ROOT_PATH}/${simulator_name}/config/ssl/full_node/private_full_node.crt" \
    --key "${SIMULATOR_ROOT_PATH}/${simulator_name}/config/ssl/full_node/private_full_node.key" \
    -d '{}' -k -H "Content-Type: application/json" https://localhost:8555/healthz

  # shellcheck disable=SC2181
  if [[ "$?" -ne 0 ]]; then
      logger "$(dt) Node healthcheck failed"
      exit 1
  fi

if [[ ${start_wallet} == "true" ]]; then
    curl -X POST --fail \
      --cert "${SIMULATOR_ROOT_PATH}/${simulator_name}/config/ssl/wallet/private_wallet.crt" \
      --key "${SIMULATOR_ROOT_PATH}/${simulator_name}/config/ssl/wallet/private_wallet.key" \
      -d '{}' -k -H "Content-Type: application/json" https://localhost:9256/healthz

    # shellcheck disable=SC2181
    if [[ "$?" -ne 0 ]]; then
        logger "$(dt) Wallet healthcheck failed"
        exit 1
    fi
fi

logger "$(dt) Healthcheck(s) completed successfully"
