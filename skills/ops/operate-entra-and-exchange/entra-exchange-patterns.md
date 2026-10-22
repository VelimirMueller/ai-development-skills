# Entra and Exchange Patterns

Reference for [operate-entra-and-exchange](./SKILL.md). Commands follow the Microsoft Graph and
Exchange Online docs as of 2026-10-22; they were not run against a live tenant while writing this
file. Anything marked *unverified* below was not confirmed against the docs.

## Rule: know which object you are editing — app registration or enterprise app

**Why:** Every app registration has a service principal (the "enterprise app"), with different
object IDs. Permissions are defined on the registration; consent, role assignments and Conditional
Access target the service principal. Half of all "my change did nothing" sessions are a correct
change applied to the wrong object.
**How to apply:** Look up both, side by side, before changing either:
`az ad app list --display-name <app-name> --query '[].{appId, objectId:id}'` and
`az ad sp list --display-name <app-name> --query '[].{id, appId}'`. Copy object IDs from that
output, never from memory or an old ticket.
**Anti-example:** Granting a role to the app registration's object ID when Graph expects the
service principal's — the call succeeds or fails depending on endpoint, and the permission never
lands.

## Rule: application permissions are standing grants — scope them or drop them

**Why:** An application permission works with nobody signed in and never expires. `Sites.ReadWrite.All`
app-only means every site in the tenant, forever. Scoping features exist precisely to avoid that:
`Sites.Selected` limits Graph access to named sites; Exchange RBAC for Applications limits app-only
`Mail.Send` to a management scope's recipients.
**How to apply:** Prefer delegated permissions when a user context exists. For app-only, take the
smallest permission and pair it with its scoping mechanism (`Sites.Selected` + per-site grant;
`Mail.Send` + `New-ManagementScope`/`New-ManagementRoleAssignment -App`). Re-sweep granted
permissions quarterly; the sweep is the audit.
**Anti-example:** `Mail.Send` application permission, tenant-wide, "because the scoped setup took
an extra hour".

## Rule: prefer federated credentials; a fresh client secret can 401 for minutes

**Why:** A federated credential has no secret to leak, rotate or sweep for expiry. A client secret
is a long-lived password; worse, right after creation or reset the new secret can fail with 401
for minutes while the change propagates — the natural reaction (reset again) invalidates the
secret you just stored and deepens the outage.
**How to apply:** Workload identity federation for CI and anything with an OIDC issuer (GitHub
Actions subject `repo:<org>/<repo>:environment:<env>` — read the exact subject with
`gh api repos/<org>/<repo>/actions/oidc/customization/sub`, new tenants embed ids). Certificates
where federation is impossible; client secrets only as a last resort, with an expiry reminder in
the expiry sweep. After a secret reset: wait a few minutes and retry before concluding failure.
**Anti-example:** Resetting a working secret three times in ten minutes because the first test
call 401'd, then deploying with secret number two while number three is the valid one.

## Rule: page through `@odata.nextLink`, and stop on 429 `Retry-After`

**Why:** Graph returns one page at a time; a script that reads only the first page processes a
random subset of the directory and reports success. Throttling (429) answers with a
`Retry-After` header — ignoring it and hammering extends the throttle window and can spill onto
other callers from the same tenant.
**How to apply:** Loop while the response has `@odata.nextLink` (pass that URL to the next `az
rest` call as-is). On 429, sleep exactly `Retry-After` seconds; cap total retries and say so in
the output. Batch changes with a small delay between calls rather than a tight loop.
**Anti-example:** A cleanup script that "disabled all stale accounts" — the first 100 of them.

## Rule: RBAC for Applications propagation takes 30 minutes to 2 hours and can look inverted

**Why:** Exchange scopes and role assignments replicate slowly. During that window a test can show
the app sending outside its scope, or failing inside it. Re-running the setup cmdlets does not
speed it up and can duplicate assignments.
**How to apply:** Create the scope and assignment, then wait 30 minutes before the first
verdict, up to 2 hours before escalating. Verify with `Get-ManagementRoleAssignment -App <app-id>`.
Plan the change so the verification lands inside a work window, not at its end.
**Anti-example:** "The scope does not work" ten minutes in — delete and recreate, twice, then
escalate an assignment that was fine after lunch.

## Rule: sweep credential expiry before it sweeps you

**Why:** A secret or certificate expiry with no owner stops a pipeline or an integration at a
random hour, and the recovery happens under pressure. Expiry dates are queryable — the incident is
always preventable and therefore always embarrassing.
**How to apply:** Monthly, per tenant:
`az ad app credential list --id <app-id>` (secrets) and the same with `--cert` (certificates),
sorted by `endDateTime`; flag anything inside 30 days. Pair with sign-in log review
(`auditLogs/signIns`) for service principals that stopped authenticating — a silent consumer is a
future expiry victim.
**Anti-example:** The only person who knew the secret's expiry date is on holiday, and the date
knows that.

## Rule: guest invitations and group changes can fail after the call returns success

**Why:** A Graph invitation POST can return 201 and still leave the guest in a pending or failed
state; group membership changes replicate. "I sent it" is not "they have access".
**How to apply:** After inviting, check `externalUserState` (expect `PendingAcceptance`). After
`az ad group member add`, read membership back with `az ad group member list --group <group>`.
Put the read-back in the same runbook step as the change.
**Anti-example:** Closing the ticket on the 201 response; the guest re-requests access a week later.

## Rule: Exchange Online runs app-only on certificates, not secrets

**Why:** `Connect-ExchangeOnline` app-only auth (`-AppId -CertificateThumbprint -Organization`)
requires a certificate; client-secret app-only is not supported for the cmdlets. Teams reach for
an interactive session instead, which no schedule can renew.
**How to apply:** One certificate per app, uploaded to the app registration, thumbprint recorded
(next to no secret value) in the secret store's inventory — [manage-secrets](../../infra/manage-secrets/SKILL.md).
Test the app-only connection before the interactive session that created it expires.
**Anti-example:** A nightly mail-flow report that depends on a human typing a password.

## When to deviate

- **No OIDC issuer and no certificate support in the consumer:** a client secret is acceptable —
  short validity (6 to 12 months), owner recorded, expiry sweep entry created in the same change.
- **Lab or sandbox tenant:** tenant-wide permissions for throwaway experiments are fine; the
  production rules apply the moment real data exists.
- **Emergency incident on prd:** a manual consent or role change is allowed with the ticket
  record; convert it to IaC or a scripted change during the follow-up.
