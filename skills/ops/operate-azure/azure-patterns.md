# Azure Patterns

Reference for [operate-azure](./SKILL.md). The traps below each come from a real "the command was
right, the result was wrong" session. Commands follow the Azure CLI docs as of 2026-10-22; they
were not run against a live tenant while writing this file — run the read-only forms first.

## Rule: set tenant and subscription in every shell

**Why:** The CLI has a *default* subscription, and it is whichever one was last set. A command run
without checking it operates on whatever that is — often a personal or dev subscription, and the
error (or worse, the success) looks identical.
**How to apply:** `az login --tenant <tenant-id>`, `az account set --subscription <subscription-id>`,
then `az account show --query id -o tsv` to confirm, in every new shell. Put the three lines in the
runbook snippet, not in your memory.
**Anti-example:** `az resource list` "to see what's here" — you see one subscription's here, and
you do not know which.

## Rule: `az resource list` sees ARM resources only; Entra objects need Graph

**Why:** Service principals, groups, users and app registrations are directory objects, not ARM
resources. They never appear in `az resource list` or `az graph query` over `Resources` — people
conclude "it does not exist" and create a duplicate.
**How to apply:** ARM resources → `az graph query` / `az resource list`. Directory objects →
`az ad app list`, `az ad sp list`, `az ad group show`, or Graph via `az rest`
([operate-entra-and-exchange](../operate-entra-and-exchange/SKILL.md)).
**Anti-example:** `az resource list --query "[?name=='<app-name>']"` returning empty, followed by
a second app registration "because the first was never created".

## Rule: RBAC grants propagate in 2–5 minutes, and `create` has no cleanup

**Why:** Azure RBAC is eventually consistent. A grant that "did not work" is usually still
propagating; retrying creates nothing, but assuming failure and re-running a *delete* removes the
one grant that was arriving. And `az role assignment create` never removes the grant it replaces —
old grants accumulate into standing access nobody tracks.
**How to apply:** After a grant, wait 2–5 minutes before diagnosing. Swapping a role: add the new
grant, confirm it works, then explicitly `az role assignment delete --id <assignment-id>`. List
before you create — `az role assignment list --assignee <object-id> --scope <scope>`.
**Anti-example:** "Fix" a permission by granting Contributor, then leaving the old Reader grant in
place forever.

## Rule: Key Vault "secret not found" is usually authorization, not existence

**Why:** A caller without the data-plane role gets a *not-found* error, not *forbidden* — the
service hides existence from unauthorised readers, and the error sends you hunting a secret that
exists. Management-plane roles (Contributor on the vault) do not grant secret *content* access.
**How to apply:** Check three things in order: the active subscription (`az account show`), the
data-plane role (`Key Vault Secrets User` on the vault for the caller), then the secret name.
`az keyvault secret list --vault-name <vault>` returning the secret but `show` failing proves it
is a data-plane role problem.
**Anti-example:** Recreating a secret (which rewrites its value and breaks every consumer) to fix
a missing `Key Vault Secrets User` role.

## Rule: `az rest` PUT replaces the whole set — GET, merge, PUT

**Why:** Most Azure PUT endpoints overwrite the entire collection. A PUT that carries only the one
setting you meant to add silently deletes every other setting. Static web app app settings are the
classic case: the app "loses" its configuration with a green command exit.
**How to apply:** GET the current set, merge with `jq`, PUT the merged document, then GET again to
confirm. One resource, one GET-PUT-GET cycle, nothing typed by hand.
**Anti-example:** `az rest --method PUT` with a hand-written two-line body on an endpoint that owns
eleven settings.

## Rule: `-o tsv` prints booleans capitalised

**Why:** `-o tsv` prints `True`/`False` with a capital first letter. A test for the lowercase
`true` fails, and scripts that compare CLI output to JSON truth values break at 2 a.m.
**How to apply:** Compare case-insensitively (`grep -qi '^true$'`) or use `-o json | jq -e` for
anything a script branches on.
**Anti-example:** `[[ $(az ... -o tsv) == "true" ]] && …` — always false, no error, wrong branch.

## Rule: firewall IP rules are temporary — write the remove before the add

**Why:** A client-IP rule on a data store is a hole in the perimeter. It is added "for five
minutes" to unblock a task and then survives for months because the session that knew about it
ended.
**How to apply:** Write both commands as a pair; run the add; work; run the remove in the same
session; verify with `network-rule list` (step 7 of the skill). If the work may outlive the
session, a permanent rule through IaC with a documented source range is the honest option.
**Anti-example:** `az sql server firewall-rule create --name temp-me ...` on a Monday; audit
finding it the next quarter.

## Rule: name `<app>-<env>-<type>`, tag everything, lock prd

**Why:** Names are the first query key and the first mental model; tags are the only thing queries
and cost reports can group by; locks are the only thing that stops a tired `delete` command.
**How to apply:** `<app>-<env>-<type>` (for example `<app>-prd-web`); tags `app`, `env`, and a
tag naming the owning system (`managed-by=<system>` makes track detection a one-liner);
`CanNotDelete` locks on prd stateful resources. All three belong in IaC, not in the CLI — the CLI
verifies them.
**Anti-example:** A prd database with no lock and no tags, named `mydb2`.

## Rule: know the cost before the month ends

**Why:** Cost surprises on Azure are found by finance, not by engineering, weeks after the cause.
`az consumption` and budgets make the same numbers visible while the resource can still be resized.
**How to apply:** `az consumption usage list --top 5 -o table` for the current month's biggest
line items; a budget with an alert contact per subscription, created through IaC where possible.
**Anti-example:** A test VM-scale-set left at max size because nobody looked at usage after the
load test.

## When to deviate

- **Break-glass on prd** (incident, pipeline broken): a hand change is allowed — record it in the
  ticket with the exact command and revert it into IaC within the same incident. The rule targets
  routine hand edits, not emergencies.
- **Subscriptions you cannot query with `az graph`** (no permission on all subscriptions): fall
  back to per-subscription `az resource list`, slower but correct.
- **A repo with its own naming and tagging standard:** the repo's standard wins; record the
  difference in its runbook.

