#!/usr/bin/env bash
# Run the accuracy evaluation as the unprivileged raqib user, under systemd filesystem, privilege and resource limits.
#   sudo bash run-eval.sh /tmp/eval.csv [concurrency]   -> starts unit "raqib-eval" in the background (survives a dropped SSH link)
#   sudo bash run-eval.sh --collect                     -> once it has finished: results in /tmp/eval-out.tar.gz
set -euo pipefail
OUT=/home/raqib/eval
APP=/home/raqib/raqib/backend

if [ "${1:-}" = "--collect" ]; then
  tar czf /tmp/eval-out.tar.gz -C "$OUT" . && chmod 644 /tmp/eval-out.tar.gz
  echo "results: /tmp/eval-out.tar.gz"
  exit 0
fi
IN="${1:?labelled url,label csv}"
CONC="${2:-2}"

rm -rf "$OUT"
install -d -o raqib -g raqib -m 0700 "$OUT"
install -o raqib -g raqib -m 0600 "$IN" "$OUT/eval.csv"
systemctl reset-failed raqib-eval 2>/dev/null || true

systemd-run --unit=raqib-eval --uid=raqib --gid=raqib --collect --quiet \
  -p StandardOutput=file:"$OUT/log.txt" -p StandardError=file:"$OUT/log.txt" \
  -p WorkingDirectory="$APP" \
  -p ProtectSystem=strict -p ProtectHome=read-only -p "ReadWritePaths=$OUT $APP/raqib/data" -p PrivateTmp=yes \
  -p NoNewPrivileges=yes -p CapabilityBoundingSet= -p ProtectKernelTunables=yes -p ProtectKernelModules=yes \
  -p ProtectKernelLogs=yes -p ProtectControlGroups=yes -p LockPersonality=yes -p MemoryMax=3G -p TasksMax=512 \
  -E HOME=/tmp -E PLAYWRIGHT_BROWSERS_PATH=/home/raqib/.cache/ms-playwright \
  -E RAQIB_CHROME_SANDBOX=1 -E RAQIB_FRESH_BROWSER=1 -E RAQIB_RADAR=0 -E RAQIB_MODE=auto \
  "$APP/.venv/bin/python" -m raqib.cli "$OUT/eval.csv" --out "$OUT/results.csv" --json "$OUT/results.json" --shots "$OUT/shots" --concurrency "$CONC"

echo "started unit raqib-eval (concurrency $CONC). Progress: systemctl is-active raqib-eval; tail $OUT/log.txt"
