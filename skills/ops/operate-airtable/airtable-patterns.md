# Airtable Patterns

Reference for [operate-airtable](./SKILL.md). API behaviour below follows the Airtable Web API
docs as of 2026-10-22; no live base was available while writing this file, so endpoint details
marked *unverified* must be re-read against the docs before first use.

## Rule: one PAT per integration, scoped to its bases

**Why:** A single token used by every script cannot be revoked without breaking everything, and
its scopes describe no one. Per-integration tokens make the blast radius of a leak one script,
and the scope list doubles as documentation of what each integration actually does.
**How to apply:** Create a PAT per integration with the narrowest scopes — `data.records:read`,
`data.records:write`, `schema.bases:read` — on exactly the bases it needs. Store per
[manage-secrets](../../infra/manage-secrets/SKILL.md); name the integration in the secret's
metadata. Audit the token list quarterly and delete the ones whose scripts are gone.
**Anti-example:** One `data.records:write` token on all bases, pasted into three repos, "until we
split it up".

## Rule: field IDs (`fld…`), not names

**Why:** Names change (a rename in the UI breaks every script that night); the same name exists
in many tables with different meanings; and select option values can carry trailing spaces, so a
value that looks equal fails a `filterByFormula` match with no error. IDs are stable and unique.
**How to apply:** Scripts reference `fld…`/`tbl…` IDs everywhere; a comment maps IDs to current
names for humans. Fetch the mapping once per run from the metadata API instead of hard-coding
names. Trim option values before comparing; never trust a copied value's whitespace.
**Anti-example:** `{"Email": "..."}` works in testing, then someone renames the column to
"Email address" and the nightly import writes nothing — with HTTP 200.

## Rule: batch at most 10 records, respect 5 requests/second, back off 30 seconds on 429

**Why:** The API rejects larger batches outright, and the rate limit is per base: one busy script
can starve every other integration on the same base. A 429 means the limit was hit; immediate
retries make the window worse and can fail the whole run.
**How to apply:** Chunk writes into requests of 10 records; keep a client-side pacing delay
below 5 rps. On 429, sleep 30 seconds and retry; cap retries and report the failed chunk rather
than looping silently. Deletes follow the same limits.
**Anti-example:** A 500-record "import" that posts one record per request, gets throttled at
record 60, retries instantly, and ends with the base rate-limited for every other consumer.

## Rule: `typecast` is a decision, not a default

**Why:** `typecast: true` silently coerces values into field types — "42" into a number, a string
into a single-select option (creating options that did not exist). That is convenient for imports
and dangerous for anything that should fail loudly on bad data.
**How to apply:** Default to `typecast` off; data errors then return 422 with the field ID, which
is what a migration wants. Turn it on for controlled imports of known-messy data, and say so in
the script header.
**Anti-example:** Typecast on for a "cleanup" script that quietly creates a new select option for
every typo it was supposed to remove.

## Rule: webhooks expire, their payloads are fetched, and their 200 proves nothing

**Why:** Three traps in one feature: webhooks expire after about 7 days unless refreshed
(*verify* the current refresh mechanism in the docs); notifications carry no data — the payload
must be fetched via the list-payloads endpoint; and a webhook pointed at the wrong base accepts
the registration with 200 while the actual change triggers nothing.
**How to apply:** Record every webhook's creation and expiry in the runbook; refresh or recreate
on a schedule shorter than the expiry. Fetch payloads after each notification; keep the payload
cursor. Verify a new webhook end to end — test write on the exact base, then a fetched payload —
before closing the ticket.
**Anti-example:** A "sync is green" dashboard fed by a webhook that expired two days after setup;
everyone checks the 200 registration, nobody checks the payloads.

## Rule: automations are deployed in the UI — a manual step is a recorded step

**Why:** The API does not create or change automations. An automation rebuilt by hand on prd
exists nowhere in the repo, so the next base rebuild loses it, and nobody knows it was there.
**How to apply:** Keep the automation's definition (trigger, actions, owning table) in the
runbook next to the base's schema diff; deploy it as an explicit checklist step with an owner
when a base is set up or promoted. Screenshot or export the configuration; Airtable has no
automation-as-code today.
**Anti-example:** A prd base recreated from the dev base after an incident; the order-confirmation
automation exists only in the old base and in someone's memory.

## Rule: never write to a table another system owns

**Why:** An automation, sync or integration writing to the same table will race your writes,
overwrite them, or break on your schema assumptions. The failure is intermittent, appears days
later, and both sides look innocent.
**How to apply:** The audit step lists tables and their writers before any write. If a table has
a writer, your access is read-only by rule; coordinate changes through the owning system's
process. Document ownership per table in the runbook.
**Anti-example:** A script "fixes" statuses in a table that an automation also updates; every
eighth fix is silently reverted within a minute.

## Rule: dev, stg and prd are separate bases, promoted with a schema diff

**Why:** Airtable has no environments — two bases that started identical drift the moment someone
renames a field on prd. Without a diff gate, a script tested on dev fails on prd (or worse,
succeeds with wrong semantics) because the schemas no longer match.
**How to apply:** One base per environment, IDs in the repo env config. CI fetches each base's
metadata (tables, fields, IDs) and diffs them; a mismatch fails the promotion. Schema changes
land on dev first, then promote; data never copies between environment bases without a ticket.
**Anti-example:** A migration script whose `filterByFormula` uses a field that exists on dev and
was renamed on prd — it matches nothing, deletes nothing, reports success.

## Rule: interface-only access is not base access

**Why:** Interface collaborators see an interface, not the base; scripts run with their PAT get
403s that look like "the base is broken". The two access models are easy to conflate when the
same person has both in different places.
**How to apply:** When a human needs script-level data access, grant it deliberately through a
PAT with base scopes — never through interface membership. When someone only needs to work data
through the UI, an interface is the least privilege, and the API is not theirs.
**Anti-example:** Granting full base access to a dozen people because one of them "kept getting
errors" running a personal export script.

## When to deviate

- **A single personal base, no other system involved:** one PAT, names instead of IDs, and no
  diff gate are tolerable — the ownership and promotion rules start mattering the moment a second
  writer or a prd base exists.
- **A one-off import where loud failures are worse than silent coercion:** `typecast` on, with
  a post-import verification by record count and field spot-check.
- **Airtable as a UI over data owned elsewhere:** treat every table as foreign-owned; the system
  of record syncs in, nothing else writes.
