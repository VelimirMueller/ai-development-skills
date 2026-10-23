# OpenTofu CI Patterns

Reference for `set-up-opentofu`. The CI is the pipeline of
[set-up-terraform-pipeline](../set-up-terraform-pipeline/SKILL.md) with `tool: tofu`: the same `ci.yml` lint stage,
`infra.yml`, `_tf-check.yml`, `_tf-plan.yml`, `_tf-apply.yml`, `deploy.yml`, `promote.yml` and `tf-drift.yml`
([workflow-templates.md](../set-up-terraform-pipeline/workflow-templates.md)). The files follow the fleet standard
(`VelimirMueller/fleet-standard`); on 2026-10-23 a repo rendered from them with the changes below passed `fleet check`
with no exception record. None has run on GitHub yet. Application delivery (image build, deploy) is
[set-up-delivery-pipeline](../set-up-delivery-pipeline/SKILL.md). Repo-side rules (layout, backend, encryption) are
[opentofu-patterns.md](./opentofu-patterns.md).

## The changes for an OpenTofu repo on Hetzner or IONOS

1. In `infra.yml`, `tf-drift.yml` and `_ci-lint.yml`: `tool: tofu`; in `infra.yml` and `tf-drift.yml`: `cloud: none`
   (no OIDC exists for Hetzner or IONOS, so there is no cloud login step).
2. In `_tf-plan.yml` and `_tf-apply.yml`, replace the job `env:` block with the block below. The values are secrets of
   the bound environment (`<env>-plan` for a plan, `<env>` for an apply), so a dev token never reaches a prd job:

   ```yaml
       env:
         TF_IN_AUTOMATION: "true"
         TF_ENCRYPTION: ${{ secrets.TF_ENCRYPTION }}                 # state and plan encryption, see opentofu-patterns.md
         AWS_ACCESS_KEY_ID: ${{ secrets.TFSTATE_ACCESS_KEY_ID }}       # state bucket credentials, not AWS
         AWS_SECRET_ACCESS_KEY: ${{ secrets.TFSTATE_SECRET_ACCESS_KEY }}
         HCLOUD_TOKEN: ${{ secrets.HCLOUD_TOKEN }}                     # keep the token of your provider
         IONOS_TOKEN: ${{ secrets.IONOS_TOKEN }}
   ```

3. The version file is `terraform/.opentofu-version`; `required_version` in `terraform/versions.tf` repeats it.
4. List every static secret in `fleet.yml` `secrets:` (SEC-07: name, scope, kind, owner, expires; never a value) and
   record the `SEC-01` exception (static tokens because the provider has no OIDC) in the same `fleet.yml`.

## Rule: apply the saved plan, not a fresh one
**Why:** `tofu apply tfplan` applies the bytes a human saw. OpenTofu re-checks the saved plan against the current state and config and refuses to apply it if either moved, so an approval cannot silently cover a different change. A plan recomputed in the apply job would include commits nobody reviewed.
**How to apply:** `_tf-plan.yml` writes `-out=tfplan` and uploads it as `tfplan-<env>-<sha>`; `_tf-apply.yml` downloads it and runs `tofu apply tfplan`. Exit 1 from plan fails the job; exit 0 skips the apply (`exitcode == '2'` gate). `tofu_wrapper: false` keeps `-detailed-exitcode` intact; the wrapper would swallow the exit code.
**Anti-example:** `tofu apply -auto-approve` in the apply job.

## Rule: the plan artifact is encrypted and lives seven days
**Why:** A saved plan holds resolved values. The `plan {}` block of `TF_ENCRYPTION` encrypts the file (verified: it starts with `{"meta":{"key_provider.pbkdf2`), so the artifact is ciphertext even inside GitHub. Seven days is the fleet maximum (CI-COST-13) and covers a long approval.
**How to apply:** `actions/upload-artifact` with `retention-days: 7` and `if-no-files-found: error`, as in `_tf-plan.yml`.

## Rule: two GitHub environments per target
**Why:** A plan needs secrets but no human; an apply needs a human for prd. `<env>-plan` holds read-only or plan-scoped secrets with no reviewers, so plans never queue behind an approval; `<env>` holds the apply secrets, and the `tf-apply-prd` gate adds the human for a prd plan with changes. The cost is that every secret is stored twice.
**How to apply:** six environments: `dev`, `stg`, `prd` and `dev-plan`, `stg-plan`, `prd-plan`, plus the gates `promote-stg`, `promote-prd`, `tf-apply-prd` (`scripts/setup-github.sh`). The secret list is in the skill (step 6); no OIDC exists for Hetzner or IONOS, so these are scoped long-lived tokens.

## Rule: no plan on a pull request; every plan and apply starts by hand
**Why:** A plan with credentials is a deploy job (CI-COST-01): a PR or a merge that runs it hands the provider token to any branch, and a merge that applies leaves no moment to read the plan. The PR runs the credential-free checks only.
**How to apply:** `infra.yml` has `workflow_dispatch` only. `deploy.yml` (dev, from `develop`) and `promote.yml` (stg, prd) start it after their guards and approvals. The plan text goes to the step summary, which the approver reads at the `tf-apply-prd` gate.

## Rule: validate without credentials
**Why:** fmt, validate, module tests, tflint and the misconfiguration scan need no cloud secrets, so they run on any PR — forks included — and fail fast before anything slow starts. `init -backend=false` skips the state store; `-lockfile=readonly` fails when the lock file does not cover the config.
**How to apply:** the `lint` stage of `ci.yml` calls `_tf-check.yml` when a `*.tf`, `*.tfvars` or lock file changed (CI-LINT-04). `tofu test` runs every `terraform/tests/` and `terraform/modules/<name>/tests/` file.

## Rule: drift is a read-only plan, started by hand
**Why:** Console edits and provider-side changes otherwise surface during an incident. `-detailed-exitcode` is the contract (verified): 0 clean, 2 changes, 1 error. The plan uses `-lock=false` because it only reads; it must not block an apply running at the same time. A schedule per repo costs minutes in every repo; the fleet-wide scan runs once, in the control repo (CI-COST-12).
**How to apply:** `tf-drift.yml`, one plan job per env with the `<env>-plan` credentials, and one `report` job that opens or closes the `drift: <env>` issue.

## Rule: one apply per environment at a time, never cancelled
**Why:** Two applies against one state interleave. The `concurrency` group `infra-<env>` on the workflow and `tf-apply-<env>` on the apply job serialise applies per environment, and `cancel-in-progress: false` means a queued run waits instead of killing an apply mid-flight — cancelling between resource operations is how state gets wedged.
**How to apply:** keep both `concurrency` blocks as in the templates.

## Pins
Every third-party action is pinned by commit SHA; versions, SHAs and the Trivy image are in
[stack-versions.md](../_shared/stack-versions.md) and the pipeline templates. `permissions: {}` at the top and explicit
grants per job; `persist-credentials: false` on every checkout.

## When to deviate
- **Private repo on GitHub Free** (no environments, no reviewers): use the `private-free` variant of the pipeline
  (workflow-templates.md): repo secrets with an `_DEV`/`_STG`/`_PRD` suffix, the dispatch as the approval, prd applied
  by `tf-apply-prd.yml`. Say in the README that the gate is a pause, not a second pair of eyes.
- **Monorepo**: give each infra root its own `infra-<root>-<env>` concurrency group and its own `working-directory`, or
  the app pipeline and infra block each other.
- **PR plan comments**: there is no PR plan to comment on; the plan goes to the step summary and the artifact.
