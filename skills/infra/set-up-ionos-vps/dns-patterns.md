# IONOS Domain and DNS Patterns

Reference for `set-up-ionos-vps`. Covers domains registered at IONOS whose DNS IONOS hosts, and the subdomains that point at self-hosted VPS. IONOS API facts come from the lego `ionos` provider docs and community code as of 2026-10-22; nothing here wrote to a live zone (list at the end).

## Rule: one explicit record per subdomain; no wildcard by default

**Why:** A wildcard (`*.example.de`) answers for every name, so a typo or a forgotten service still resolves to your server, and a scanner finds hosts you never meant to publish. Explicit records also document which box serves which name.

**How to apply:** Per hostname an `A` record (and `AAAA` if the VPS has IPv6) to the VPS IP. Several subdomains on one box: one record each, all with the same IP; Traefik routes by `Host()`. Use `CNAME` only for a name that follows another name you control, never at the apex. Keep the record list in the private inventory ([vps-hardening-patterns.md](./vps-hardening-patterns.md#rule-one-private-inventory-never-in-a-public-repo)).

**Anti-example:** `*.example.de A <ip>` "so new services just work" — and a stale `old.example.de` keeps getting a certificate.

## Rule: a new subdomain in the panel is not empty — clean it first

**Why:** "Add subdomain" in the IONOS panel publishes a default record set for the new label. Measured on a real subdomain (2026-09-08): an `A` to the IONOS parking page (`217.160.0.64`), an `AAAA`, two `MX` (`mx00`/`mx01.ionos.de`) and `TXT "v=spf1 include:_spf-eu.ionos.com ~all"`. Your new `A` record then sits next to the parking `A`, so half the lookups land on the parking page. A `CNAME` cannot coexist with any other record at the same name (RFC 1034 §3.6.2, RFC 2181 §10.1), so the panel refuses it.

**How to apply:** After adding a subdomain, delete all five default records for that label, then add the records you want: an `A`/`AAAA` to the VPS, or one `CNAME` to an external target. Enter the **label only** as host name (`watch`, not `watch.example.de`); IONOS appends the zone. Check with `dig +short A <name>` (exactly one address) and `dig +short MX <name>` (empty, or the null MX).

**Anti-example:** Adding the VPS `A` record and leaving the parking `A` in place — the site works on one resolver and shows a parking page on the next.

## Rule: drop the TTL before a move, raise it after

**Why:** Resolvers cache a record for its TTL. With a TTL of 1 day, a move to a new VPS takes a day to reach everyone.

**How to apply:** Normal TTL 3600. One TTL period before a planned move, set 300; move; check; set 3600 again.

## Rule: CAA names the one CA that may issue

**Why:** Without CAA, any public CA may issue a certificate for your name. With it, a CA must refuse unless it is listed.

**How to apply:** At the apex: `CAA 0 issue "letsencrypt.org"` and `CAA 0 issuewild ";"` (no wildcards) unless you use a DNS-01 wildcard; add `CAA 0 iodef "mailto:<you>"`. CAA is inherited by subdomains that have no own CAA record. Check: `dig +short CAA example.de`.

## Rule: a name that sends no mail says so

**Why:** A domain without SPF and DMARC is easy to spoof: phishing "from" your domain is accepted by receivers that have nothing to check against. IONOS adds MX records for its own mail and a soft SPF (`~all`) to new names (see the rule on new subdomains).

**How to apply:** On every domain and subdomain that sends no mail:
- `TXT "v=spf1 -all"`
- `_dmarc TXT "v=DMARC1; p=reject; adkim=s; aspf=s"`
- null MX: `MX 0 .` — and delete the default IONOS MX records if you do not use IONOS mail.

A subdomain that serves only HTTP gets `v=spf1 -all` as well; DMARC at the apex covers subdomains through `sp=` (default: the `p=` value).

**Anti-example:** Keeping IONOS's default MX "in case" while mail runs elsewhere — bounces and spoofing both get easier.

## Rule: set reverse DNS for every VPS IP

**Why:** Mail receivers and some APIs check that the IP's PTR record matches a name that resolves back to it. IONOS asks for it before it unblocks outbound port 25. It also makes logs and abuse reports readable.

**How to apply:** In the Cloud Panel, set the PTR of each VPS IP to its main name (`watch.example.de`), and make sure that name has an `A` record to the same IP (forward-confirmed reverse DNS). Check: `dig +short -x <ip>`.

## Rule: HTTP-01 by default; DNS-01 only for wildcards and private hosts

**Why:** HTTP-01 needs only port 80 and no credential. DNS-01 needs an API key that can change every record of the domain — on IONOS it is an account key, so a leak hands over the whole DNS (and with it TLS and mail for the domain).

**How to apply:**
- Default: Traefik `certificatesResolvers.le.acme.httpChallenge.entryPoint=web`, port 80 open in the firewall policy ([compose-patterns.md](../deploy-to-hetzner/compose-patterns.md)).
- Wildcard, or a host not reachable from the internet (behind WireGuard): DNS-01 with lego's `ionos` provider, `certificatesResolvers.dns.acme.dnsChallenge.provider=ionos`, credential `IONOS_API_KEY` in the form `<prefix>.<secret>` (or `IONOS_API_KEY_FILE`). Optional tuning: `IONOS_PROPAGATION_TIMEOUT`, `IONOS_POLLING_INTERVAL`, `IONOS_TTL`.
- Create the key at the IONOS developer portal (`developer.hosting.ionos.de`). Store it as a secret ([manage-secrets](../manage-secrets/SKILL.md)), mount it as a file, never as image `ENV` or in a compose file in git. One key per host that needs it, so you can revoke one without the others.

## Rule: know which IONOS DNS API you are talking to

**Why:** IONOS has two DNS APIs with different hosts and credentials. Docs and SDKs mix them up, and a key for one gets 401 at the other.

**How to apply:**
- **Hosting DNS API** — for domains bought at IONOS: `https://api.hosting.ionos.com/dns/v1`, header `X-API-Key: <prefix>.<secret>`. List zones with `GET /zones`, add records with `POST /zones/{zoneId}/records` (body: `name`, `type`, `content`, `ttl`, `prio`, `disabled`). This is the one lego's `ionos` provider uses.
- **IONOS Cloud DNS** — for IONOS Cloud datacenters ([deploy-to-ionos](../deploy-to-ionos/SKILL.md)): `https://dns.de-fra.ionos.com`, Cloud API token. Not for a VPS domain.

Read-only first check, without printing the key:

```bash
curl -fsS -H "X-API-Key: $(cat ~/.config/ionos/dns-api-key)" https://api.hosting.ionos.com/dns/v1/zones | jq -r '.[].name'
```

## Rule: record changes go through one path

**Why:** Records edited by hand in the panel and by a script drift apart, and nobody knows which is right.

**How to apply:** For a handful of names, the Cloud Panel plus the inventory file is enough. Once you script records (more than about ten names, or records that follow deploys), make the script or tofu the only writer and treat the panel as read-only.

## When to deviate

- **Many short-lived preview hosts:** a wildcard record plus a DNS-01 wildcard certificate is fine — on a dedicated subdomain (`*.preview.example.de`), not the apex.
- **The domain sends mail:** replace the null-mail records with real SPF, DKIM from the mail provider, and DMARC that starts at `p=none` with reports, then moves to `p=reject`.
- **DNS hosted elsewhere** (Cloudflare, Hetzner DNS): the record rules stay the same; the API section does not apply.
- **DNSSEC:** turn it on at the registrar if IONOS offers it for the TLD; check `dig +dnssec`. Not covered here.

## Not verified against a live IONOS account

- The Hosting DNS API paths, header and record body (taken from lego's docs and community scripts, not from a call).
- Whether a Hosting API key can be scoped to one zone (no IONOS statement found; treat it as account-wide).
- The default record set on a new **apex** domain (measured only for a subdomain).
- The PTR field location in the Cloud Panel for a VPS.
