#!/usr/bin/env bash
# Install the Raqib code for the unprivileged raqib user. No API keys are copied into the VM.
#   sudo bash install-app.sh /tmp/raqib.tar.gz /tmp/dist.tar.gz
set -euo pipefail
SRC="${1:?code archive}"; DIST="${2:?frontend dist archive}"
APP=/home/raqib/raqib
export DEBIAN_FRONTEND=noninteractive

rm -rf "$APP"
mkdir -p "$APP/frontend"
tar xzf "$SRC" -C "$APP"
tar xzf "$DIST" -C "$APP/frontend"
rm -f "$APP/.env"  # belt and braces: the archive is made from git, which never holds .env
chown -R raqib:raqib "$APP"

cd "$APP/backend"
sudo -u raqib -H python3 -m venv .venv
sudo -u raqib -H .venv/bin/pip install -q --upgrade pip
sudo -u raqib -H .venv/bin/pip install -q -r requirements.txt
sudo -u raqib -H .venv/bin/python -m playwright install chromium chromium-headless-shell
.venv/bin/python -m playwright install-deps chromium || echo "WARNING: playwright install-deps failed; install Chrome's libraries manually"
apparmor_parser -r /etc/apparmor.d/raqib-chromium
echo "installed $(sudo -u raqib -H .venv/bin/python -c 'import raqib; print(raqib.__version__)' 2>/dev/null || true)"
