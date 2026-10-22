# Alerting Patterns

Reference for [set-up-alerting](./SKILL.md). Signals, resource attributes and the SLO burn-rate
method: [observability.md](../../core/_shared/observability.md); the log field names queries match:
[logging-contract.md](../../core/_shared/logging-contract.md).

## Rule: alert on symptoms users feel, not causes

**Why:** A CPU alert wakes someone without telling them whether a user is hurt. A symptom alert
(error rate, latency, failed jobs, queue age) maps to harm a user can describe; a cause is only a
guess about which symptom it might produce.
**How to apply:** Build the catalogue from symptoms: error rate, latency SLO burn rate (two windows,
the defaults in [observability.md](../../core/_shared/observability.md)), failed jobs, oldest
message age in a queue. Causes (CPU, memory, disk, pool saturation) go on dashboards; alert on them
only when they are themselves the user-visible incident (disk full → uploads fail).
**Anti-example:** P1 on 90% CPU at 04:00, steady for a year, while the real outage is a queue that
stopped draining.

## Rule: severity P0–P3 decides the route

**Why:** Severity is a routing decision, not a mood. If everything is P1, the on-call triages noise
instead of incidents.
**How to apply:** One table, kept in the catalogue and mirrored in the alert name (`[P<n>]`):

| Severity | Meaning | Route |
|---|---|---|
| P0 | users hurt now, service down or data at risk | page (phone/on-call) |
| P1 | users hurt soon or a key feature degraded | chat channel |
| P2 | one job or one flow failed, users barely notice | ticket |
| P3 | trend worth watching | weekly digest |

Page only for user-visible harm now. Everything else survives a night.
**Anti-example:** "Let's make it P1 to be safe" — two such decisions and the P1 channel is muted.

## Rule: every alert carries a runbook link, an owner, and service and environment labels

**Why:** An alert nobody owns is an alert nobody answers. Without `service` and `environment`
labels, staging noise pages production people.
**How to apply:** Name format `[P<n>][<env>] <service> — <symptom>`; description carries runbook URL
and owner; every query filters on `service.name` and `deployment.environment.name` (the values from
[observability.md](../../core/_shared/observability.md)). The owner is a role or team placeholder
that survives personnel changes (`<owner>`), not a person.
**Anti-example:** "High latency somewhere" — no service, no env, no runbook, no owner.

## Rule: thresholds are per environment

**Why:** The same absolute number means different things at different traffic. One error in ten dev
requests is noise; one in ten prd requests is a burning SLO. A threshold that fits prd pages dev
every afternoon; one that fits dev never fires in prd.
**How to apply:** Thresholds are variables, values in `terraform/envs/<env>.tfvars`, one row per
alert per env in the catalogue. Prefer ratios over absolute counts at low traffic, and minimum-count
guards (`and count > N`) so a 3-of-4 ratio does not page.

## Rule: alerts are code, promoted with the service

**Why:** Rules configured by hand in the UI drift silently and cannot be reviewed or rolled back.
Rules applied by a separate observability workflow that runs only from `main` never reach stg — a
rule can fire in prd that never ran anywhere else. Alerts and the code they watch must move
together, or the alert describes a system that no longer exists.
**How to apply:** Alert resources live in the same Terraform root per environment as the rest,
applied by the same pipeline and promoted by the same promotion:
[set-up-terraform-pipeline](../../infra/set-up-terraform-pipeline/SKILL.md),
[branch-promotion](../../core/_shared/branch-promotion.md). One state per environment.
**Anti-example:** A nightly cron that syncs rules from a spreadsheet into the backend API.

## Rule: after apply, read the rules back and assert each exists exactly once

**Why:** An apply can half-fail. A rename can leave the old rule and the new rule both firing. A
rule that points at a deleted channel sends nothing and still looks green in the pipeline.
**How to apply:** After every apply, list rules through the API and assert: each catalogue name
appears exactly once (`sort | uniq -d` empty, `grep -cxF` = 1), and every channel reference resolves
to an existing channel. Fail the pipeline job on a mismatch.
**Anti-example:** Trusting a green `apply` and finding out at 03:00 that the "duplicate" was two
copies of the same rule paging two channels.

## Rule: one route per alert

**Why:** Two delivery paths for one rule mean two cards. The on-call reads both, investigates once,
and mutes the louder one — which then stays muted when it becomes the only path.
**How to apply:** Each rule references exactly one channel. Audit catch-all and default route
policies monthly: a rule matched by both its own route and a catch-all is the classic duplicate.
**Anti-example:** "Add the on-call channel to every alert for visibility" — every card arrives
twice, one channel gets muted.

## Rule: test-fire every new alert in dev

**Why:** An untested alert is a hope. A typo in a query fails in silence forever — nothing fires,
and nothing warns that nothing fires. Only a real event proves query, threshold, window and route.
**How to apply:** In dev, trigger one real matching event: a request that returns 500, one forced
`fatal` log line, one skipped heartbeat emission. Expect one card, once, on the right channel. Then
resolve it and confirm it clears. Zero cards = broken query or route; two = duplicate routes.

## Rule: expect deploy-induced alerts

**Why:** A deploy is a controlled incident: jobs restart mid-run, the old version errors during
rollout, queues drain slowly. A "job failed" alert can fire on its own deploy, every deploy, until
the team mutes it — and then it stays muted.
**How to apply:** Before the alert ships, ship the tolerance for deploy-time failures: the job
alerts on final failure (with retry window), not first failure. Check alert history after each
deploy; a rule that fires on every deploy gets fixed or silenced by a maintenance window (see
below), never by muting the channel.

## Rule: never alert on a gauge with a lifetime maximum

**Why:** A monotonic gauge (total since process start) only goes up. A threshold on its raw value
fires once and stays fired — forever, across restarts of the process and of the humans reading it.
**How to apply:** Alert on the window, not the total: `increase(gauge[10m])` or `rate(gauge[10m])`
above a threshold. Restart-resets of the gauge then read as "nothing new", which is the truth.
**Anti-example:** `total_errors > 1000` — fires on day one, still firing two months later.

## Rule: a negative filter also matches a missing field

**Why:** In log query languages, `field != 'x'` is true when the field is absent. A filter meant to
catch the bad value matches every line that has no value at all.
**How to apply:** Guard the negative: `field EXISTS AND field != 'x'`. Run the query against real
logs from the window before saving the rule — the hit count tells you if unrelated lines slipped in.
**Anti-example:** `status != 'ok'` pages on every access log line that carries no `status` at all.

## Rule: severity and label values are case-sensitive

**Why:** `severity = 'P1'` does not match `p1`, `P1 ` or `prio1`. A filter that matches nothing
fails silently — the alert never fires.
**How to apply:** Emit label values from one set of constants (the catalogue), never by hand at the
call site; or compare lowercased on both sides. The test-fire in dev is the proof; it catches this
class of bug in minutes.
**Anti-example:** One service logs `level = 'ERROR'`, another `error`; the P0 rule matches only one.

## Rule: log-based alerts match the exact attribute the exporter writes

**Why:** A resource attribute (`service.name`, `deployment.environment.name`, set once by the
collector — [deploy-otel-collector](../../infra/deploy-otel-collector/SKILL.md)) and a field in the
log body are different things to the query engine. Same word, different path, zero matches.
**How to apply:** Open one real log line in the backend, copy the field path from it, then write the
query. Field names follow [logging-contract.md](../../core/_shared/logging-contract.md) (`level`,
`event`, `error.type`); casing per that contract is lowercase for levels.

## Rule: heartbeat/absence alerts for cron jobs and pipelines

**Why:** A job that fails to start writes no error log — the failure mode is silence. A nightly e2e
run disabled by accident is invisible until the regression it would have caught reaches prd.
**How to apply:** The job emits one completion event (`event = 'job.completed'`); the alert fires
when the count over the period plus slack (25 h for a nightly) is below one. Pipelines get the same
treatment: alert when a scheduled workflow has not succeeded in its period.

## Rule: alert on CI/CD health

**Why:** A pipeline that cannot deploy is an outage that has not happened yet. Drift and stale
approvals block releases quietly: a run waiting at a gate blocks every later run of that
environment, and a week-old saved plan must be rejected, not approved.
**How to apply:** One digest alert per environment, route P2: failed deploy runs in 24 h, an open
drift issue, pending deployments older than a few hours. The drift job and the approval gates come
from [set-up-terraform-pipeline](../../infra/set-up-terraform-pipeline/SKILL.md).

## Rule: notification channels are part of the alert code

**Why:** A channel renamed by hand breaks every route that referenced it — silently, the read-back
excepted. Channel sprawl (three "oncall" channels, two dead) is how cards land where nobody looks.
**How to apply:** Channels (Slack, Teams, email, webhook) are resources next to the rules,
referenced by id, asserted by the read-back. One channel per route from the severity table. Webhook
URLs land in state — one dedicated, revocable webhook per channel, rotated on schedule
([manage-secrets](../../infra/manage-secrets/SKILL.md)).

## Rule: maintenance windows for planned deploys

**Why:** Disabling a rule during a deploy is how a rule stays disabled. The deploy noise is
predictable and bounded; the window names it and ends on its own.
**How to apply:** A maintenance window per environment covering the deploy window, with an end time.
Silence the deploy-induced rules (job failed, error rate), never the P0 user-facing burn alerts for
longer than the deploy takes. The window is code or a scheduled API call, not a person's memory.

## Rule: review alert noise monthly

**Why:** Alert rot is certain: thresholds drift, services change, an alert everyone ignores is an
outage you find out about from users. The review is the only force that pushes back.
**How to apply:** Once a month, read firing counts per rule from the API against the catalogue.
Every alert must be actionable: if it fired twice without action, lower the severity, fix the
threshold, or delete it. Delete is a valid outcome; the catalogue row goes too.

## When to deviate

- **No traffic baseline yet** (new service, no SLO data): alert on any 5xx in prd plus a heartbeat,
  and upgrade to burn-rate alerts when a baseline exists — the same call
  [observability.md](../../core/_shared/observability.md) makes.
- **A backend with no code surface** (legacy platform, rules only in its UI): keep the manual rules,
  record them in the catalogue as manual, and still run the read-back — the assertion works against
  any API, not only Terraform-created rules.
- **A personal or internal-only tool**: a weekly digest email can be the entire setup. Severity
  routing for a system with no on-call is theater; say so instead of half-building it.
- **Active incident**: temporary rules are fine while it burns; each one joins the next monthly
  review and is either promoted into the catalogue or deleted.
