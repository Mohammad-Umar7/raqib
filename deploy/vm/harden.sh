#!/usr/bin/env bash
# Harden the Raqib sandbox VM (Ubuntu Server). Run once as root from the admin account:
#   sudo bash harden.sh <admin-user>
# Files it installs (same folder): nftables.conf, raqib-chromium.apparmor, raqib.service
set -euo pipefail
ADMIN="${1:?usage: harden.sh <admin-user>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
export DEBIAN_FRONTEND=noninteractive

# Never lock ourselves out: key login must already work for the admin before passwords are switched off.
test -s "/home/$ADMIN/.ssh/authorized_keys" || { echo "no SSH key for $ADMIN yet: refusing to disable password login"; exit 1; }

echo "== 0. DNS first: public, non-filtering resolvers (the host firewall stops VirtualBox relaying DNS to the home router)"
mkdir -p /etc/systemd/resolved.conf.d
cat > /etc/systemd/resolved.conf.d/90-raqib.conf <<'EOF'
[Resolve]
DNS=1.1.1.1 8.8.8.8
Domains=~.
EOF
systemctl restart systemd-resolved

echo "== 1. security updates (and keep them coming)"
apt-get update -q
apt-get -y -q full-upgrade
apt-get -y -q install unattended-upgrades nftables python3-venv python3-pip ca-certificates curl apparmor-utils dnsutils
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

echo "== 2. unprivileged scanner user: no password, no sudo"
id raqib &>/dev/null || adduser --disabled-password --gecos "" raqib
chmod 750 /home/raqib

echo "== 3. SSH: keys only, admin only, no forwarding"
cat > /etc/ssh/sshd_config.d/10-raqib.conf <<EOF
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers $ADMIN
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
EOF
sshd -t
systemctl try-reload-or-restart ssh.service 2>/dev/null || true  # socket-activated on 22.10+: new connections read the config anyway

echo "== 4. kernel: no IPv6, fewer kernel info leaks"
cat > /etc/sysctl.d/90-raqib.conf <<'EOF'
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
kernel.unprivileged_bpf_disabled = 1
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2
EOF
sysctl --system >/dev/null

echo "== 6. firewall: public web only"
install -m 0644 "$HERE/nftables.conf" /etc/nftables.conf
systemctl enable nftables
nft -f /etc/nftables.conf

echo "== 7. AppArmor: let Chrome's own sandbox start"
install -m 0644 "$HERE/raqib-chromium.apparmor" /etc/apparmor.d/raqib-chromium
apparmor_parser -r /etc/apparmor.d/raqib-chromium

echo "== 8. dashboard service (installed, not started)"
install -m 0644 "$HERE/raqib.service" /etc/systemd/system/raqib.service
systemctl daemon-reload

echo "hardened"
