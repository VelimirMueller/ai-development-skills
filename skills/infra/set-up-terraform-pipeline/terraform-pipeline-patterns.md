# Terraform Pipeline Patterns

Reference for [set-up-terraform-pipeline](./SKILL.md). One rule per design decision and per safety rule of the
pipeline. The promotion contract this implements is
[branch-promotion](../../core/_shared/branch-promotion.md); the file-by-file content is
[workflow-templates.md](./workflow-templates.md). No company, tenant, subscription or account identifiers appear in
this file — use `<org>`, `<repo>`, `<app>` and the placeholders shown.

## Rule: resolve the environment in one `setup` job
**Why:** Every later job needs the same answer to "which environment am I?". Derived in several places it drifts, and a
PR event names the ref `<n>/merge`, which maps to no environment.
**How to apply:** One `setup` job is the single source of truth. Push: `develop→dev`, `stage→stg`, `main→prd`, anything
else fails. `pull_request`: plan `dev` (base develop) or `prd` (hotfix into main), mode plan. `workflow_dispatch`:
allowed pairs only `refs/heads/develop@dev`, `refs/heads/stage@stg`, `refs/heads/main@prd` (a `case` statement);
everything else fails. Downstream jobs read the env from the `setup` output — never from `github.ref_name`.
**Anti-example:** `environment: ${{ github.ref_name }}` on a PR event.

## Rule: ref@env binding is server-side, not just YAML
**Why:** A dispatch runs the workflow file from the dispatched ref, so a workflow edit on an older branch is the
workflow that runs. Only the environment's deployment branch policy survives that.
**How to apply:** Give every environment a deployment branch policy: `dev` → `develop`, `stg` → `stage`, `prd` → `main`,
`dev-plan` → `develop` plus PR refs. The `setup` case statement and the branch policy must agree; the policy is the
enforcement, the case statement is the fast-fail.
**Anti-example:** Relying on `if:` guards in the workflow to keep a `prd` apply off a `develop` dispatch.

## Rule: concurrency is keyed on the resolved environment, with a PR clause
**Why:** Two applies against one state interleave; two PR plan runs may cancel each other, which is fine. One key from a
raw ref name would serialize unrelated runs and cancel a deploy mid-flight.
**How to apply:** Workflow level:
`group: infra-${{ github.event_name == 'pull_request' && format('pr-{0}', github.event.number) || github.ref_name }}`
with `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`. Apply job:
`group: tf-apply-<env>` with `cancel-in-progress: false` — `<env>` from the `setup` output.
**Anti-example:** `cancel-in-progress: true` on the apply job — cancelling between resource operations is how state
gets wedged.

## Rule: save the plan, then apply only the saved plan
**Why:** `apply tfplan` applies the exact bytes a human saw. Terraform/OpenTofu re-checks the saved plan against the
current state and config and refuses a stale one, so an approval cannot silently cover a different change. A plan
recomputed in the apply job would include commits nobody reviewed.
**How to apply:** Plan writes `-out tfplan`, uploads `tfplan-<env>-<sha>` (tfplan, plan.txt, plan.json; retention 7
days; never uploaded on failure). Apply downloads it, verifies it exists, plan.txt is non-empty and the sha matches,
then runs `apply tfplan`.
**Anti-example:** `apply -auto-approve` on a fresh plan in the apply job.

## Rule: `-detailed-exitcode` is the contract, and it fails closed
**Why:** Exit 0 means no changes, 2 means changes, 1 means error. Treating 1 as "no changes" would skip an apply on a
planning error — the exact moment a resource breaks silently.
**How to apply:** Capture the exit code with `set +e` / `set -e`; map 0 → `has_changes=0`, 2 → `has_changes=1` (and
record `destroys`), 1 → fail the job. `tofu_wrapper: false` (or `terraform_wrapper: false`) so the wrapper does not
swallow the exit code.
**Anti-example:** `|| true` after the plan, or `echo $?` without checking it.

## Rule: the gate exists only on prd, and only when there are changes
**Why:** A gate on dev or stg adds a human to a step already covered by `promote-stg`; a gate on "no changes" is a
pause with nothing to review. Fail-closed: a missing or unknown `has_changes` value must not mean "apply anyway".
**How to apply:** `has_changes == 0` → no gate, no apply, "no changes" in the summary. `dev`, `stg` → apply without a
second human gate. `prd` and `has_changes != 0` → the `tf-apply-prd` gate. Plan exit 1 always fails.
**Anti-example:** `if: always()` before a prd apply, or gating the dev apply.

## Rule: every destroy or replace is listed before the apply
**Why:** A destroy/replace on prd deletes live data or restarts stateful resources. The approver must see it at the top
of the plan, not buried in a 60k-character summary.
**How to apply:** After the plan, `show -json` and count `create`/`delete`/`replace` actions. On prd, print
`⚠ N to destroy, M to replace` at the top of the summary, listed by address. Include `update` on attributes named
`sku*`, `size`, `tier`, `instance_type` in the "replace-like" list (*unverified* heuristic).
**Anti-example:** Sending the raw plan text with no guard, so a destroy scrolls past the approver.

## Rule: previews run with the read-only plan identity and `-lock=false`
**Why:** A lock-holding PR plan once orphaned the dev state lease for 10.5 hours. Only the push-triggered plan that
feeds an apply needs the lock. The plan identity must be provably read-only, so a compromised plan step cannot write.
**How to apply:** PR plans, dispatch plans and drift plans run as the plan identity with `-lock=false`. The
plan job asserts its effective client id is the plan identity (`az account show --query user.name` /
`aws sts get-caller-identity`); the apply job asserts its `ARM_CLIENT_ID` (or role ARN) equals the committed writer for
that environment in a closed table (`.github/deploy-identities.yaml`).
**Anti-example:** One privileged identity for both plan and apply, so a PR plan holds a write-capable token.

## Rule: `ARM_*` and role variables are job-level, never workflow-level
**Why:** Workflow-level `env:` is inherited by every job — including the credential-free `check` job and any job that
later calls out. Identifiers should not travel to steps that do not need them.
**How to apply:** Declare `ARM_USE_OIDC`, `ARM_CLIENT_ID`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` (or the role ARN) on
the plan and apply jobs only, as environment **variables** (they are not secrets).
**Anti-example:** A workflow-level `env:` block carrying `ARM_CLIENT_ID` to the `check` job.

## Rule: read the OIDC subject from the API, never invent it
**Why:** The subject template differs by account (`repo:<org>/<repo>:…` vs the id-embedded form). A guessed subject
means a federated credential that never matches, and the failure looks like an auth error.
**How to apply:** `gh api repos/<org>/<repo>/actions/oidc/customization/sub`; append `:environment:<env>`. The setup
script prints the exact string; copy it into the Azure federated credential or the AWS trust policy.
**Anti-example:** Hard-coding `repo:<org>/<repo>:environment:prd` on a repo whose subject embeds ids.

## Rule: Azure backend uses `use_azuread_auth`, no storage account keys
**Why:** A storage account key in a state backend is a long-lived credential that Terraform embeds; Azure AD auth (OIDC)
gives a fresh token per call and survives key rotation.
**How to apply:** Backend `azurerm` with `use_azuread_auth = true` and `use_oidc = true`, one storage account per env,
container `tfstate`, key `<app>-<env>.tfstate`, blob lease lock. The plan identity needs `Storage Blob Data Reader`
(Contributor for the lock-holding branch plan); the apply identity gets scoped Contributor.
**Anti-example:** `access_key = ...` or a SAS token in `backend.tf`.

## Rule: one exact tool version, checked three ways
**Why:** A `plan` and an `apply` run by different Terraform versions can disagree about the plan file, and a provider
constraint that drifts from the lock file fails `init`.
**How to apply:** One exact version in `.terraform-version` (or `.opentofu-version`), `required_version` in `versions.tf`,
and the setup action in the workflow must all agree; the check job fails if they do not. Lock for
`linux_amd64`, `linux_arm64`, `darwin_arm64`; CI runs `init -lockfile=readonly`.
**Anti-example:** `required_version = ">= 1.0"` while CI pins `~> 1.7` — two configs that only disagree in prd.

## Rule: never read a secret with a data source
**Why:** `data "azurerm_key_vault_secret"` / `data "aws_secretsmanager_secret_version"` fails the whole plan when the
secret does not exist yet — every unrelated change blocks on a secret that was not created in the right order.
**How to apply:** Create the secret as a resource (value set once, `lifecycle { ignore_changes = [value] }`) or pass it
by reference. Audit greps for both data sources and fails on them.
**Anti-example:** A data source for a secret that a later PR's resource creates.

## Rule: swap role assignments in two applies
**Why:** RBAC propagates over 2–5 minutes; destroying the old grant before the new one exists means a window where
nothing has access — and destroys can run before creates.
**How to apply:** Add the new grant in one apply, remove the old one in the next apply. Two PRs or two commits, never
one plan that drops and adds the same principal in the same run.
**Anti-example:** Replacing `azurerm_role_assignment` in place, which plans `-/+` and leaves a gap.

## Rule: force-new renames destroy — plan them before the first apply
**Why:** `name` on most Azure resources is `ForceNew`, so a rename plans `-/+`: the old resource is destroyed and a new
one created. In a PR stack, a rename in a later PR destroys what an earlier PR just applied.
**How to apply:** Rename before the first apply of the resource, or use `moved {}` where the provider supports it. On prd
a `-/+` needs an explicit decision, not a silent approval.
**Anti-example:** Renaming a database in a follow-up PR and letting the plan delete the one the first PR built.

## Rule: `prevent_destroy` on stateful prd resources
**Why:** The one guard that stops an accidental `destroy` before it runs. Databases, storage accounts and key vaults hold
state that a delete cannot recover.
**How to apply:** `prevent_destroy = true` on stateful prd resources; rely on the destroy/replace guard for the rest.
**Anti-example:** A prd database with no lifecycle guard and a plan that renames its `name`.

## Rule: recover a stale lock by matching it, never by guessing
**Why:** A cancelled run can leave the state lock held (an Azure blob lease is never released). Force-unlocking the wrong
lock breaks a running apply; guessing the id is how two applies end up on one state.
**How to apply:** Confirm no run is in progress, match the lock's created time to a cancelled run, then
`terraform force-unlock <ID>` (or `az storage blob lease break`). Keep `timeout-minutes` on plan and apply jobs so a hung
run ends and the lock is visible.
**Anti-example:** `force-unlock` of the newest lock while a pipeline is still running.

## Rule: reject a stale waiting run instead of approving a days-old plan
**Why:** A run parked at `tf-apply-prd` blocks every later run of that environment. Approving it days later applies a
plan built against long-gone state — it fails as "Saved plan is stale", or worse, applies something nobody remembers.
**How to apply:** Reject superseded pending deployments before starting a new run:
`gh api -X POST repos/<org>/<repo>/actions/runs/<id>/pending_deployments -f state=rejected`. When an apply fails with
"Saved plan is stale", annotate "start a new run, do not re-run this job".
**Anti-example:** Re-running the stale apply job, or leaving the old run waiting and approving it a week later.

## Rule: `defaults.run.shell: bash` gives `-eo pipefail`
**Why:** The default shell for `run:` is `sh -e`, not `sh -eo pipefail`. Without `pipefail`, `terraform plan | tee
plan.txt` reports the exit code of `tee`, so a failed plan looks green.
**How to apply:** `defaults: { run: { shell: bash } }` at workflow level (bash enables `-eo pipefail`). Read the plan's
exit code via `${PIPESTATUS[0]}` where you pipe.
**Anti-example:** A `| tee` step with no pipefail and no explicit exit-code capture.

## Rule: one always-running `conclusion` job is the required check
**Why:** A path-filtered workflow that does not run on a given PR reports no required check, and a branch protection rule
with no status to wait on is not a rule. All per-env jobs run only sometimes, so none of them can be the required
context.
**How to apply:** A `conclusion` job that always runs, succeeds when the relevant checks passed (or were skipped), and is
the single required status on `develop`. Use `dorny/paths-filter` inside it if you must narrow.
**Anti-example:** Making the `plan` job the required check on `develop` and wondering why infra-only PRs never merge.

## Rule: downstream jobs require apply success, never `always()`
**Why:** A rejected approval or a failed apply must not still ship the app or run the migration. `always()` and
`!failure()` both let a skipped/cancelled apply slide through.
**How to apply:** App deploy, migrate and smoke jobs declare `needs.apply.result == 'success'`, or an explicit
"no changes" skip. Nothing depends on the apply with a broad `always()`.
**Anti-example:** `needs: apply` with `if: always()` so the deploy runs even when the apply was rejected.

## Rule: no destroy-as-rollback
**Why:** A rollback that runs `plan -destroy` + apply is a different, untested code path invoked only under pressure. The
forward path is the only path.
**How to apply:** A rollback is a promotion/deploy of an older SHA (application) or a revert PR (infra, forward-only).
The audit greps for `plan -destroy` and `destroy` scripts and fails on them.
**Anti-example:** A "rollback" workflow that terraform-destroys the environment and reapplies an old plan.

## Rule: scheduled jobs never bind a gated environment
**Why:** A schedule bound to an environment with required reviewers waits forever — there is no human to approve a cron
job. The drift job needs read-only credentials and no gate.
**How to apply:** `tf-drift.yml` runs under `<env>-plan` (no reviewers). It plans with `-lock=false`; exit 2 opens/updates
one issue per env `drift: <env>`, exit 1 fails, exit 0 is clean.
**Anti-example:** A weekly drift job bound to `prd` that queues behind the `tf-apply-prd` reviewers.

## Rule: alerts promote with the code
**Why:** An observability workflow that only applies from `main` never reaches `stg`, so `stg` alerts and `prd` alerts
diverge and a change cannot be tested before it gates prd.
**How to apply:** The SigNoz provider (or equivalent) lives in the same root, one state per environment, applied by the
same pipeline and the same promotion. After apply, read the rules back and assert each exists exactly once and its routes
resolve.
**Anti-example:** A separate `alerts.yml` that `apply`-s only when `github.ref == 'refs/heads/main'`.

## Rule: the promotion push uses an App token, not `GITHUB_TOKEN`
**Why:** A push made with `GITHUB_TOKEN` does not trigger other workflows, so the fast-forward to `stage`/`main` would
never start the deploy pipeline.
**How to apply:** `actions/create-github-app-token` mints an installation token; the `push` job re-verifies the
fast-forward and runs `git push origin "$SHA:refs/heads/<branch>"` (no `--force`). The App id and private key live as
secrets of `promote-stg`/`promote-prd`.
**Anti-example:** Pushing `stage` with `github.token` and discovering the stg deploy never ran.

## When to deviate

- **One environment, no stage:** drop `stage`/`stg` and keep the same rules for `main`; promotion is `main :=
  develop@<sha>` behind `promote-prd`, and `tf-apply-prd` still gates only changes.
- **Terragrunt monorepo:** one root per unit, no workspaces. Give each root its own backend config and concurrency
  group, keep the plan-artifact rule per root, and keep one `setup` job resolving the environment for all of them.
- **Terraform Cloud / HCP remote runs:** the plan/apply split moves into TFC/HCP; GitHub keeps the promotion, the
  approval gate and the drift job, but the saved-plan artifact and `-detailed-exitcode` handling do not apply — say so,
  and keep `prevent_destroy`, the destroy/replace guard and the secret-data-source rule.
- **Private repo on a plan without environment reviewers:** the `tf-apply-prd` gate degrades to a pause in front of the
  plan summary. That is not a second pair of eyes — say so in the README, do not pretend it is.
