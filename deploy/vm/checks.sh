#!/usr/bin/env bash
# Prove the sandbox lockdown. Run as root inside the VM:  sudo bash checks.sh | tee sandbox-checks.txt
set -u
APP=/home/raqib/raqib/backend
HERE="$(cd "$(dirname "$0")" && pwd)"
asr() { sudo -u raqib -H env HOME=/tmp PLAYWRIGHT_BROWSERS_PATH=/home/raqib/.cache/ms-playwright RAQIB_CHROME_SANDBOX=1 "$@"; }
pass=0; fail=0
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS  $name"; pass=$((pass + 1)); else echo "FAIL  $name"; fail=$((fail + 1)); fi; }
blocked() { ! asr curl -s -m 5 -o /dev/null "$1"; }

echo "== Raqib sandbox checks · $(date -u +%FT%TZ) · $(. /etc/os-release; echo "$PRETTY_NAME") · kernel $(uname -r)"
echo "-- network, from the scanner's own user"
check "public web reachable (https://example.com)" asr curl -sf -m 10 -o /dev/null https://example.com
check "home router 192.168.1.1 blocked" blocked http://192.168.1.1/
check "home router 192.168.0.1 blocked" blocked http://192.168.0.1/
check "private 10.0.0.1 blocked" blocked http://10.0.0.1/
check "private 172.16.0.1 blocked" blocked http://172.16.0.1/
check "the host through VirtualBox (10.0.2.2:8600) blocked" blocked http://10.0.2.2:8600/
check "VirtualBox DNS proxy (10.0.2.3) blocked" blocked http://10.0.2.3:53/
check "cloud metadata 169.254.169.254 blocked" blocked http://169.254.169.254/
check "carrier NAT 100.64.0.1 blocked" blocked http://100.64.0.1/
check "DNS-rebinding name (192-168-1-1.nip.io) blocked" blocked http://192-168-1-1.nip.io/
check "DNS works through the public resolvers" asr dig +short +time=3 example.com @1.1.1.1
check "IPv6 switched off" test "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)" = 1
check "firewall table loaded" nft list table inet raqib

echo "-- secrets and accounts"
check "no .env in the app" test ! -e /home/raqib/raqib/.env
check "no API key, token or GitHub credential on disk" bash -c '! grep -rIlE "sk-ant-(api|admin)[0-9]{2}-[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}" /home /etc /opt /root 2>/dev/null'
check "no key in any process environment" bash -c '! grep -lsaE "ANTHROPIC_API_KEY=.|SERPAPI_KEY=." /proc/[0-9]*/environ'
check "scanner user cannot sudo" bash -c 'sudo -l -U raqib | grep -q "not allowed"'
check "SSH password login off" bash -c 'sshd -T | grep -qi "^passwordauthentication no"'
check "SSH root login off" bash -c 'sshd -T | grep -qi "^permitrootlogin no"'

echo "-- browser (Raqib's own launch settings)"
cp "$HERE/browser_checks.py" "$APP/browser_checks.py" && chown raqib:raqib "$APP/browser_checks.py"
if (cd "$APP" && asr .venv/bin/python browser_checks.py); then pass=$((pass + 1)); else fail=$((fail + 1)); fi

echo "-- blocked attempts the firewall logged in the last 15 minutes"
journalctl -k --since "-15 min" --no-pager 2>/dev/null | grep -o 'raqib-drop-[a-z0-9]*' | sort | uniq -c
nft list ruleset | grep -E 'counter packets [1-9]' | sed 's/^\s*/  /'

echo "== $pass passed, $fail failed"
[ "$fail" -eq 0 ]
