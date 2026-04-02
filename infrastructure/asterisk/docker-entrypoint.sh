#!/bin/sh
set -e

# Значения по умолчанию, чтобы Asterisk не падал на getaddrinfo("MCN_...") при пустом .env
export SIP_SERVER_IP="${SIP_SERVER_IP:-127.0.0.1}"
export SIP_OPERATOR_IP="${SIP_OPERATOR_IP:-$SIP_SERVER_IP}"
export SIP_USER="${SIP_USER:-notconfigured}"
export SIP_PASSWORD="${SIP_PASSWORD:-notconfigured}"

if ! command -v envsubst >/dev/null 2>&1; then
  echo "docker-entrypoint: envsubst not found" >&2
  exit 1
fi

envsubst '${SIP_SERVER_IP} ${SIP_USER} ${SIP_PASSWORD} ${SIP_OPERATOR_IP}' \
  < /templates/pjsip.conf.template > /etc/asterisk/pjsip.conf

chown asterisk:asterisk /etc/asterisk/pjsip.conf 2>/dev/null || true

AST_BIN=$(command -v asterisk)
if [ -z "$AST_BIN" ]; then
  echo "docker-entrypoint: asterisk binary not found" >&2
  exit 1
fi
if id asterisk >/dev/null 2>&1; then
  exec su -s /bin/sh asterisk -c "exec $AST_BIN -f"
fi
exec "$AST_BIN" -f
