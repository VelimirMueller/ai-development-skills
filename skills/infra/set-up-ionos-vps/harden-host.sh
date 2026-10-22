#!/usr/bin/env bash
# First-boot hardening for a fresh IONOS VPS on Debian 13 (trixie). Idempotent: a second run
# changes nothing. Run as root over the key-based session that ssh-copy-id set up:
#
#   ssh root@<ip> 'ADMIN_USER=admin SWAP_MB=2048 bash -s' < harden-host.sh
#
# It refuses to switch off password and root login until the admin user holds a key.
# Rules and reasons: vps-hardening-patterns.md.
set -euo pipefail

ADMIN_USER="${ADMIN_USER:-admin}"
SWAP_MB="${SWAP_MB:-2048}"               # 0 = no swap file
EXTRA_SSH_USERS="${EXTRA_SSH_USERS:-}"   # e.g. "deploy" for the forced-command deploy user
REBOOT_TIME="${REBOOT_TIME:-04:30}"
JOURNAL_MAX="${JOURNAL_MAX:-200M}"

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }
# Names land in sudoers and sshd_config: reject anything that is not a plain user name.
name_re='^[a-z_][a-z0-9_-]{0,31}$'
[[ "$ADMIN_USER" =~ $name_re ]] || { echo "invalid ADMIN_USER: $ADMIN_USER" >&2; exit 1; }
for u in $EXTRA_SSH_USERS; do
  [[ "$u" =~ $name_re ]] || { echo "invalid user in EXTRA_SSH_USERS: $u" >&2; exit 1; }
done
[[ "$SWAP_MB" =~ ^[0-9]+$ ]] || { echo "SWAP_MB must be a number" >&2; exit 1; }
# shellcheck source=/dev/null
. /etc/os-release
[[ "${VERSION_CODENAME:-}" == "trixie" ]] || echo "warning: tested on Debian 13 trixie, found ${VERSION_CODENAME:-unknown}" >&2

export DEBIAN_FRONTEND=noninteractive
# ssh forwards the client locale (macOS: LC_CTYPE=UTF-8), which Debian does not have.
export LC_ALL=C.UTF-8
apt-get update -qq
apt-get -y -qq upgrade
apt-get -y -qq install sudo unattended-upgrades apt-listchanges needrestart \
  fail2ban python3-systemd ca-certificates curl

# Admin user with sudo; it takes over root's authorized keys.
if ! id "$ADMIN_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$ADMIN_USER"
fi
usermod -aG sudo "$ADMIN_USER"
install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "/home/$ADMIN_USER/.ssh"
if [[ -s /root/.ssh/authorized_keys && ! -s "/home/$ADMIN_USER/.ssh/authorized_keys" ]]; then
  install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" /root/.ssh/authorized_keys "/home/$ADMIN_USER/.ssh/authorized_keys"
fi
# Key-only login means sudo needs a password the user never had: allow sudo without one.
echo "$ADMIN_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$ADMIN_USER"
chmod 440 "/etc/sudoers.d/90-$ADMIN_USER"
visudo -cq

# sshd: the first value read wins, and Include sits at the top of sshd_config, so 10- beats
# a provider's 50-cloud-init.conf that sets PasswordAuthentication yes.
if ssh-keygen -lf "/home/$ADMIN_USER/.ssh/authorized_keys" >/dev/null 2>&1; then
  cat > /etc/ssh/sshd_config.d/10-hardening.conf <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers $ADMIN_USER${EXTRA_SSH_USERS:+ $EXTRA_SSH_USERS}
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
EOF
  sshd -t
  systemctl reload ssh
else
  echo "skip sshd lock-down: /home/$ADMIN_USER/.ssh/authorized_keys holds no valid key" >&2
fi

# Security updates every day, reboot in a fixed window when a kernel or libc needs it.
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat > /etc/apt/apt.conf.d/52unattended-upgrades-local <<EOF
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "$REBOOT_TIME";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF

# fail2ban reads the journal: trixie ships no rsyslog, so there is no /var/log/auth.log.
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled  = true
backend  = systemd
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
fail2ban-client -t >/dev/null
systemctl enable --now fail2ban >/dev/null 2>&1 || true
systemctl reload-or-restart fail2ban 2>/dev/null || true

# Swap: a 1-2 GB VPS without it gets OOM-killed on the first apt upgrade or image pull.
if [[ "$SWAP_MB" -gt 0 ]] && ! swapon --show=NAME --noheadings | grep -q .; then
  [[ -f /swapfile ]] || fallocate -l "${SWAP_MB}M" /swapfile
  chmod 600 /swapfile
  # A file left by an aborted run has no swap signature yet.
  blkid -p -s TYPE -o value /swapfile 2>/dev/null | grep -qx swap || mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness = 10' > /etc/sysctl.d/90-swappiness.conf
sysctl -q --system >/dev/null 2>&1 || true

# Journal cap: a 20 GB disk fills with logs before anyone looks.
install -d /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/10-size.conf <<EOF
[Journal]
SystemMaxUse=$JOURNAL_MAX
EOF
systemctl restart systemd-journald 2>/dev/null || true

echo "--- verify"
sshd -T 2>/dev/null | grep -E '^(permitrootlogin|passwordauthentication|allowusers) '
fail2ban-client status sshd 2>/dev/null | grep -E 'Currently banned|Total failed' || true
swapon --show
