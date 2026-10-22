# IONOS VPS Hardening Patterns

Reference for `set-up-ionos-vps`. Target: an IONOS VPS (Cloud Panel product) on Debian 13 "trixie" ([stack-versions.md](../_shared/stack-versions.md)). The script these rules describe is [harden-host.sh](./harden-host.sh); it ran twice in a `debian:trixie` container. Two findings come from live IONOS VPS work on 2026-10-22 (the `50-cloud-init.conf` override and the `ufw limit` refusal). IONOS facts come from the IONOS help pages as of 2026-10-22; what was not checked on a live VPS is listed at the end.

## Rule: the password only opens the door once — keys first, then lock

**Why:** A fresh VPS takes root logins with a password from the whole internet. Bots try within minutes. A password typed into an agent's command or a chat ends up in logs and transcripts.

**How to apply:**
1. The person runs `ssh-copy-id -i ~/.ssh/<key>.pub root@<ip>` and types the password once. No agent reads it, no file stores it.
2. Run `harden-host.sh`: it creates the admin user, copies root's key to it, and only then writes the sshd drop-in. If the admin has no key, the script skips the lock-down instead of locking everyone out.
3. Keep the root session open, prove `ssh admin@<ip> sudo true` in a second terminal, then close the first.
4. Afterwards change the root password in the Cloud Panel or set it to a random value nobody keeps: password login is off, so the old one should not be valid anywhere.

**Anti-example:** `sshpass -p "$(pbpaste)" ssh root@…` — the password lands in the process list and shell history, and the server still accepts it.

## Rule: the sshd drop-in must sort before the provider's

**Why:** Debian's `sshd_config` reads `Include /etc/ssh/sshd_config.d/*.conf` at the top, and for most keywords **the first value read wins**. The IONOS Debian 13 VPS image ships `50-cloud-init.conf` with `PasswordAuthentication yes` (seen on a live VPS on 2026-10-22: password login stayed on after editing `sshd_config`, with 8246 failed logins in 24 h). A hardening file named `99-hardening.conf`, or an edit of the main file, loses to it silently.

**How to apply:** Name the file `10-hardening.conf`: `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `AuthenticationMethods publickey`, `AllowUsers <admin> [deploy]`, `MaxAuthTries 3`, `LoginGraceTime 30`, no X11 or agent forwarding. Check the effective value, not the file: `sshd -T | grep -E '^(permitrootlogin|passwordauthentication) '`. In the container test this showed `no` / `no` with a `50-cloud-init.conf` that said `yes`. On trixie the unit is `ssh`, not `sshd`: `systemctl reload ssh`.

**Anti-example:** Editing `/etc/ssh/sshd_config` in place — the next `openssh-server` upgrade asks about the changed file, and an unattended upgrade keeps the old one.

## Rule: the Cloud Panel policy is the firewall; Docker bypasses the host one

**Why:** IONOS puts every VPS behind a network firewall that you manage in the Cloud Panel (Network → Firewall Policies). Its rules apply to **inbound** traffic only. On the host, Docker writes its own iptables/nftables rules for published ports, and they skip ufw. A `ports: "5432:5432"` in Compose is open to the internet even with `ufw deny 5432`. The panel policy sits outside the server, so it holds.

**How to apply:**
- One policy per role. Inbound: TCP 22, 80, 443; UDP 51820 only on a WireGuard host. Delete every default rule you do not use. Restrict 22 to a fixed source IP if you have one; otherwise keep it open and let keys and fail2ban do the work.
- In Compose, bind internal ports to loopback (`"127.0.0.1:8080:8080"`) or publish none and route through Traefik. The policy is the outer wall, loopback binding is the inner one.
- ufw or nftables on the host is optional. If you add it, treat it as a second layer for non-Docker services only, and use `ufw allow 22/tcp`, **not** `ufw limit 22/tcp`: `limit` rejects the 6th new connection within 30 s from one IP, which reads as "Connection refused" and breaks CI deploys and scripted checks (several SSH calls each). fail2ban counts only failed logins, so it does the job without that side effect.
- **Outbound port 25 is blocked** by IONOS on VPS and Cloud Servers. The block sits in the IONOS network, not in the policy. To lift it, the server needs a fixed hostname, a reverse DNS (PTR) entry and an SPF record, then IONOS support unblocks it. For alerts, use an HTTPS API (ntfy, a mail provider's API) or submission on 587 to a relay; that 465/587 are open is reported by third parties, not by IONOS (unverified).

**Anti-example:** "ufw is on, so the database port is closed" on a Docker host.

## Rule: updates install themselves; reboots happen in a window

**Why:** A small self-hosted box gets no attention for weeks. Unpatched OpenSSH or a kernel bug is the most likely way in.

**How to apply:** `unattended-upgrades` with `20auto-upgrades` (daily) and `52unattended-upgrades-local`: `Automatic-Reboot "true"`, `Automatic-Reboot-Time "04:30"`, `Remove-Unused-Dependencies "true"`. `needrestart` restarts services after library updates. Docker from `download.docker.com` is **not** in the default origins: plan a monthly manual `apt upgrade` for it, as in [hetzner-patterns.md](../deploy-to-hetzner/hetzner-patterns.md).

**Anti-example:** Automatic reboots on a host whose containers do not have `restart: unless-stopped` — the box comes back, the service does not.

## Rule: fail2ban reads the journal on trixie

**Why:** Debian 12 and 13 install no rsyslog, so `/var/log/auth.log` does not exist. A jail that points at it starts and bans nobody.

**How to apply:** Install `fail2ban` and `python3-systemd`; `jail.d/sshd.local` with `backend = systemd`, no `logpath`. `maxretry = 5`, `findtime = 10m`, `bantime = 1h`. Check with `fail2ban-client -t` and `fail2ban-client status sshd`. fail2ban slows brute force; it is not the protection — key-only login is.

## Rule: a deploy user gets a key, a forced command and nothing else

**Why:** CI holds the deploy key in a secret store you do not control. If it leaks, the key should run one script, not open a shell. A user in the `docker` group is root-equivalent.

**How to apply:** Follow [deploy-script.md](../_shared/deploy-script.md): `deploy` user with a locked password, key prefixed `restrict,command="/opt/deploy/run.sh"`, and an sshd `Match User deploy` block with `PermitTTY no`, `AllowTcpForwarding no`, `X11Forwarding no`. Add it to `AllowUsers` (`EXTRA_SSH_USERS=deploy`). Pin the host key in CI (`DEPLOY_KNOWN_HOSTS`); never trust on first use.

## Rule: give a 1–2 GB VPS swap, and cap the journal

**Why:** With 1 GB RAM and no swap, the OOM killer hits during `apt upgrade`, an image pull, or a burst of requests, and picks the biggest process — often the one that matters. On a 20 GB disk the journal and Docker logs fill the disk before anyone looks.

**How to apply:** A swap file of 1–2× RAM (`SWAP_MB=2048` on 1 GB), `vm.swappiness = 10` so it is a safety net and not working memory. `journald.conf.d/10-size.conf` with `SystemMaxUse=200M`. Docker: `daemon.json` with the `local` log driver and rotation ([hetzner-patterns.md](../deploy-to-hetzner/hetzner-patterns.md)). Set `mem_limit` per container so one service cannot starve the rest.

**Anti-example:** Swap as a plan for running a service that needs 2 GB on a 1 GB box. Swap catches peaks; it does not double the RAM.

## Rule: the size decides the role

**Why:** A box that is too small for its job fails at the worst time — under load, during an incident. A telemetry backend that is down during an outage is no help.

**How to apply:**

| RAM / disk | Good role | Why not more |
|---|---|---|
| 1 GB / 20 GB | Outside watcher: Gatus or Uptime Kuma (HTTP, TLS expiry, DNS checks, status page), heartbeat checks for cron and backups, ntfy; WireGuard bastion; static site; small reverse proxy | SigNoz needs ClickHouse (4–8 GB). Grafana LGTM is about 1–1.5 GB on its own. Postgres under real load needs page cache |
| 2–4 GB / 40–80 GB | One Compose app with Postgres and Traefik; light metrics and logs (VictoriaMetrics + VictoriaLogs + Grafana, about 0.5–0.7 GB, no traces) | No headroom for a second environment or a model |
| 8 GB+ | The full app stack, SigNoz, a small CPU model | — |

Put the watcher at a **different provider** from what it watches: when that provider has an outage, the watcher still sees it and still alerts.

## Rule: snapshots are an undo button, not a backup

**Why:** IONOS keeps **one snapshot per server and deletes it after 3 days**. It lives in the same account as the server. It protects a risky change; it does not protect against a lost account, a deleted server or a problem found after a week.

**How to apply:**
- Snapshot right before a risky change (dist-upgrade, a new firewall policy), delete it after the check.
- Images in the Cloud Panel (manual or scheduled) for "rebuild this box"; they are not compressed and cost storage.
- Data that matters goes **off the box and off the account**: restic or borg to Object Storage or another provider, nightly, with a quarterly restore drill ([compose-patterns.md](../deploy-to-hetzner/compose-patterns.md)). A watcher box with only config needs no data backup: its config lives in git.

## Rule: measure the hardening, then raise it where the score says

**Why:** "Hardened" without a number drifts. A scanner shows what is still open and proves that a change helped.

**How to apply:** `apt install lynis && lynis audit system --quick`; note the hardening index in the inventory. The baseline above is the floor. For a box that faces the internet with real data, the next round that raised a live IONOS VPS from 72 to 79 on 2026-10-22: an SSH crypto drop-in (`mlkem768x25519-sha256`/`sntrup761x25519-sha512`/`curve25519` KEX, chacha20 and AES-GCM ciphers, ETM MACs, `LogLevel VERBOSE`), LLMNR and mDNS off, `auditd` rules for identity files, SSH keys, sshd and Docker, fail2ban `recidive` (1-week bans), `UMASK 027`, `/dev/shm` with `noexec`, kernel modules for rare protocols and filesystems blocked. Test the CI deploy right after the crypto change: an old SSH client in a runner may share no algorithm with the server.

## Rule: one private inventory; never in a public repo

**Why:** IPs, hostnames and which box runs what are the map an attacker wants, and the first thing lost when only one person knows them.

**How to apply:** Keep `ops/inventory.md` (or the personal knowledge base) private: per VPS the name, IONOS plan, RAM/CPU/disk, IP, role, firewall policy name, admin user; per domain the registrar, DNS host, records and what each subdomain serves. Never store passwords or API keys there — only where they live ([manage-secrets](../manage-secrets/SKILL.md)).

## When to deviate

- **The box needs no SSH from the internet** (a WireGuard bastion exists): close 22 in the policy for everyone except the bastion's address.
- **A fixed admin IP:** allow 22 only from it; fail2ban becomes optional.
- **Several people administer the box:** one named user per person instead of a shared `admin`, and sudo with a password (`NOPASSWD` off).
- **Mail must leave the box directly:** do the port 25 unblock (hostname, PTR, SPF, support call) and add DKIM and DMARC before the first message.
- **The workload outgrows the VPS:** move to IONOS Cloud or Hetzner with tofu ([deploy-to-ionos](../deploy-to-ionos/SKILL.md), [deploy-to-hetzner](../deploy-to-hetzner/SKILL.md)) instead of stacking more services on the box.

## Not verified on a live IONOS VPS

- The default rules in a new VPS firewall policy (the help page says only "mandatory ports" for connecting are open), and whether a policy covers several servers.
- The KVM console as the way back in after an SSH lock-out.
- Open outbound 465/587.
