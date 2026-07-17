#!/usr/bin/with-contenv bashio
set -e

ADDRESS="$(bashio::config 'address')"
SOCKET_DIR="$(bashio::config 'socket_dir')"
INTERVAL="$(bashio::config 'interval')"
CONNECT_ATTEMPTS="$(bashio::config 'connect_attempts')"
BLUETOOTH_TIMEOUT="$(bashio::config 'bluetooth_timeout')"
SCAN_TIMEOUT="$(bashio::config 'scan_timeout')"
READ_TIMEOUT="$(bashio::config 'read_timeout')"
RECONNECT_BACKOFF="$(bashio::config 'reconnect_backoff')"
RECONNECT_BACKOFF_MAX="$(bashio::config 'reconnect_backoff_max')"
NOT_FOUND_BACKOFF_MAX="$(bashio::config 'not_found_backoff_max')"
DEBUG="$(bashio::config 'debug')"

if [[ -z "${ADDRESS}" || "${ADDRESS}" == "null" ]]; then
  bashio::exit.nok "Option 'address' is required, for example EC:B1:B6:05:FB:2A"
fi

mkdir -p "${SOCKET_DIR}"

ARGS=(
  "/app/heater_daemon.py"
  "--address" "${ADDRESS}"
  "--daemon"
  "--socket-dir" "${SOCKET_DIR}"
  "--interval" "${INTERVAL}"
  "--connect-attempts" "${CONNECT_ATTEMPTS}"
  "--bluetooth-timeout" "${BLUETOOTH_TIMEOUT}"
  "--scan-timeout" "${SCAN_TIMEOUT}"
  "--read-timeout" "${READ_TIMEOUT}"
  "--reconnect-backoff" "${RECONNECT_BACKOFF}"
  "--reconnect-backoff-max" "${RECONNECT_BACKOFF_MAX}"
  "--not-found-backoff-max" "${NOT_FOUND_BACKOFF_MAX}"
)

if bashio::var.true "${DEBUG}"; then
  ARGS+=("--debug")
fi

bashio::log.info "Starting HCalory BLE daemon for ${ADDRESS}"
bashio::log.info "Socket directory: ${SOCKET_DIR}"
exec python3 "${ARGS[@]}"
