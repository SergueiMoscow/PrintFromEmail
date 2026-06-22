#!/bin/bash
set -e

echo "[entrypoint] Starting CUPS daemon..."
cupsd

echo "[entrypoint] Waiting for CUPS scheduler..."

for i in $(seq 1 15); do
    if lpstat -r 2>/dev/null | grep -q "scheduler is running"; then
        echo "[entrypoint] CUPS is ready"
        break
    fi

    if [ "$i" -eq 15 ]; then
        echo "[entrypoint] ERROR: CUPS failed to start"
        exit 1
    fi

    sleep 1
done

echo "[entrypoint] Registering printer:"
echo "  Name : ${PRINTER_NAME}"
echo "  URI  : ${PRINTER_URI}"
echo "  Model: ${PRINTER_MODEL}"

lpadmin -x "${PRINTER_NAME}" 2>/dev/null || true

lpadmin \
    -p "${PRINTER_NAME}" \
    -E \
    -v "${PRINTER_URI}" \
    -m "${PRINTER_MODEL}"

lpadmin -d "${PRINTER_NAME}"
cupsenable "${PRINTER_NAME}"
# accept "${PRINTER_NAME}"

echo "[entrypoint] Registered printers:"
lpstat -p

echo "[entrypoint] Default printer:"
lpstat -d

echo "[entrypoint] Starting mail-print-agent..."
exec python -m app.main