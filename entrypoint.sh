#!/bin/bash
set -e

echo "[entrypoint] Starting CUPS daemon..."
cupsd

echo "[entrypoint] Waiting for CUPS to become ready..."
for i in $(seq 1 10); do
    if lpstat -H >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "[entrypoint] Registering printer: ${PRINTER_NAME} -> ${PRINTER_URI}"
lpadmin -p "${PRINTER_NAME}" -E -v "${PRINTER_URI}" -m everywhere
lpadmin -d "${PRINTER_NAME}"
cupsenable "${PRINTER_NAME}"

echo "[entrypoint] Printer registered. Starting mail-print-agent..."
exec python -m app.main
