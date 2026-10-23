---
name: set-up-terraform-pipeline
description: Use when a repo runs Terraform or OpenTofu on GitHub Actions — Azure or AWS via OIDC, develop/stage/main promotion with approval gates, manual deploys only, saved plans applied after approval, drift detection, fleet-standard conformant.
---

# Set Up Terraform Pipeline

Infrastructure changes follow the same branch-promotion contract as application code: one plan per
environment, a human approves the plan, `apply` runs only the saved plan — never a re-plan. Contract:
[branch-promotion](../../core/_shared/branch-promotion.md). This skill generates the full pipeline; the
file-by-file content is [workflow-templates.md](./workflow-templates.md), the reasons are
[terraform-pipeline-patterns.md](./terraform-pipeline-patterns.md). The files follow the fleet standard
(`VelimirMueller/fleet-standard`); a repo made from them passes `fleet check` with no exception record. Every plan
and apply starts by hand (`workflow_dispatch`): a merge or a push deploys nothing.

## 1. Audit current state (change nothing)

```bash
cat .claude/stack-profile.md 2>/dev/null          # iac, cloud, ci, runtime_manager
ls .github/workflows terraform/ infra/ 2>/dev/null
grep -rn "uses:" .github/workflows 2>/dev/null | grep -vE "@[0-9a-f]{40}" | grep -v "uses: \./"   # unpinned actions
gh api repos/{owner}/{repo}/environments --jq '.environments[].name' 2>/dev/null
gh api repos/{owner}/{repo}/rulesets --jq '.[].name' 2>/dev/null
gh api repos/{owner}/{repo}/actions/oidc/customization/sub 2>/dev/null    # OIDC subject template
git branch -r | grep -E 'origin/(develop|stage|main)$'                    # all three branches exist?
grep -rn -E 'data "(azurerm_key_vault_secret|aws_secretsmanager_secret_version)"' --include='*.tf' . 2>/dev/null
grep -rn -E 'plan -destroy|(terraform|tofu) destroy' .github scripts 2>/dev/null                    # destroy-as-rollback
```

From the profile: `iac` (terraform/opentofu/none), `cloud` (azure/aws), `ci` (must be github-actions). If there is no
profile, detect from the files above; suggest `set-up-stack-profile` when the answers change the output.

## 2. Decide what to do

- No workflows and no `terraform/`/`infra/` → full setup (steps 3 to 7).
- Workflows exist but break rules (floating tags, `-auto-approve` on a fresh plan, static cloud keys, no `permissions:{}`,
  a plan or apply on `push` or `pull_request`, a `schedule`, no `concurrency` or `timeout-minutes`) → apply only the
  delta; list each fix before editing. `fleet check .` lists the breaks by rule ID.
- Everything already follows [terraform-pipeline-patterns.md](./terraform-pipeline-patterns.md) → exit "already in
  place", run step 7, stop.
- Tell the user in one line which of the three applies.

## 3. Detect the track

| Axis | Tracks |
|---|---|
| Tool | `terraform` (HashiCorp) / `tofu` (OpenTofu — also enable state+plan encryption, see [set-up-opentofu](../set-up-opentofu/SKILL.md)) |
| Cloud | `azure` (azurerm backend, `use_azuread_auth`) / `aws` (s3 backend, `use_lockfile`) |
| Layout | new (single `terraform/` root) / existing per-env dirs (`environments/<env>/<region>/`) — keep the layout, adapt only `init`/`-var-file` lines |

## 4. Prepare the repo once (needs admin)

`scripts/setup-github.sh <owner/repo> <reviewer-login> <app-id>` (in [workflow-templates.md](./workflow-templates.md))
creates, idempotently: the nine GitHub environments (`dev`/`stg`/`prd`, `dev-plan`/`stg-plan`/`prd-plan`,
`promote-stg`/`promote-prd`, `tf-apply-prd`), one user reviewer on every gate environment (self-review allowed,
no admin bypass), the deployment branch policies, one ruleset per branch (`develop`, `stage`, `main`; the promotion
App is the only bypass actor on `stage` and `main`), and the OIDC subject read-out. Public repos only: a private
repo on GitHub Free has no environments or rulesets (`private-free` variant in the templates). Create and install the promotion GitHub App
by hand first (Contents: write on this repo only); the script only adds it as the ruleset bypass actor. Run it, then create the cloud
identities it prints the subject for:

Azure — one app registration (or user-assigned managed identity) per environment, plan and apply:

```bash
gh api repos/<org>/<repo>/actions/oidc/customization/sub
# Newer repos present an id-embedded subject: repo:<org>@<org-id>/<repo>@<repo-id>:environment:<env>.
# Take the prefix exactly as the API (or the first AADSTS700213 error) shows it; never copy another repo's.
SUB_PREFIX="repo:<org>/<repo>"     # replace with the exact prefix
az ad app create --display-name "<app>-<env>-tf-plan" --sign-in-audience AzureMyOrg
az ad app create --display-name "<app>-<env>-tf-apply" --sign-in-audience AzureMyOrg
fic() { az ad app federated-credential create --id "$1" --parameters \
  "{\"name\":\"$2\",\"issuer\":\"https://token.actions.githubusercontent.com\",\"subject\":\"${SUB_PREFIX}:environment:$2\",\"audiences\":[\"api://AzureADTokenExchange\"]}"; }
fic <plan-app-object-id>  "<env>-plan"   # the plan identity is bound to the <env>-plan environment
fic <apply-app-object-id> "<env>"        # the apply identity is bound to the <env> environment
az role assignment create --assignee <plan-app-id> --role Reader --scope "/subscriptions/<subscription-id>"
az role assignment create --assignee <plan-app-id> --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<sa>/blobServices/default/containers/tfstate"
az role assignment create --assignee <apply-app-id> --role Contributor --scope "/subscriptions/<subscription-id>/resourceGroups/<rg>"
```

AWS — one IAM role per environment, plan and apply, trusted on the GitHub OIDC provider:

```bash
aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com --thumbprint-list <thumbprint>
# trust.json: Principal.Federated = arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com,
#   Action = sts:AssumeRoleWithWebIdentity, Condition aud = sts.amazonaws.com,
#   sub = repo:<org>/<repo>:environment:<env>-plan  (trust-plan.json)
#   sub = repo:<org>/<repo>:environment:<env>       (trust-apply.json)
aws iam create-role --role-name "<app>-<env>-plan" --assume-role-policy-document file://trust-plan.json
aws iam create-role --role-name "<app>-<env>-apply" --assume-role-policy-document file://trust-apply.json
aws iam attach-role-policy --role-name "<app>-<env>-plan" --policy-arn <read-only-state-policy-arn>
```

Wait ~3 minutes after creating an Azure federated credential before the first run. There are no static cloud keys. These `az` and `aws` commands are *unverified* — they were not run against a live subscription or account; re-check the current CLI syntax and your exact scope before use.

## 5. Generate the workflows

Copy from [workflow-templates.md](./workflow-templates.md), then fill in the placeholders:

| File | Role |
|---|---|
| `.github/workflows/ci.yml` | PR check: `changes`, `lint` (workflow lint + Terraform checks), `unit`, `e2e` (dispatch only), `build`, `conclusion` (the required check). |
| `.github/workflows/_ci-lint.yml` | The `lint` stage: actionlint + zizmor, and `_tf-check.yml`. Credential-free. |
| `.github/workflows/infra.yml` | Entry point, dispatch only. `setup` resolves env from ref, then `plan`, `gate` (prd only, only if changes), `apply`, `smoke`, `tf-conclusion`. No logic beyond wiring. |
| `.github/workflows/_tf-check.yml` | One job: version-pin guard, `fmt -check -recursive`, `validate` every env with `init -backend=false`, `test`, tflint, trivy config. |
| `.github/workflows/_tf-plan.yml` | OIDC login, `init`, `plan -detailed-exitcode -out tfplan`, destroy/replace count, summary, upload `tfplan-<env>-<sha>`. |
| `.github/workflows/_tf-apply.yml` | Download `tfplan-<env>-<sha>`, verify it, `apply tfplan`. Binds `environment: <env>`. |
| `.github/workflows/deploy.yml` | `dev` deploy, dispatch on `develop`: `setup` (ref + green PR check guard) → `deploy-dev` (starts `infra.yml`, waits). |
| `.github/workflows/promote.yml` | `setup` → `preflight` (ff check, invariant, previous env green, nothing in flight, changelog) → `e2e` (stg) → `promote-stg` / `promote-prd` (approval, App-token fast-forward, deploy, wait). Targets `stg`, `prd`, `stg-hotfix`. |
| `.github/workflows/branch-sync.yml` | On push: assert `main ⊆ stage ⊆ develop`; open the back-merge PR or the reconcile issue. |
| `.github/workflows/branch-policy.yml` | Required check: PR into `stage` fails; PR into `main` passes only `hotfix/*`. |
| `.github/workflows/tf-drift.yml` | Read-only plan per env, started by hand; exit 2 opens one issue per env. |
| `.github/workflows/tf-apply-prd.yml` | `private-free` repos only: apply a saved prd plan by run id. |
| `scripts/deploy-env.sh` | Starts `infra.yml` on a branch and waits for the run of the SHA. |
| `.github/actionlint.yaml`, `.github/zizmor.yml`, `.tflint.hcl`, `.github/dependabot.yml` | config |
| `terraform/` | the root: fixed file set, `envs/<env>.tfvars` + `envs/<env>.backend.hcl`, `.terraform-version`, lock file |
| `scripts/setup-github.sh` | the step-4 idempotent setup |

Keep the rules from the templates: pin every third-party `uses:` to a full SHA with the version in a trailing comment;
`permissions: {}` at workflow level; `persist-credentials: false` on every checkout; one exact tool version.

## 6. Wire

- **Environment variables, not secrets:** `ARM_USE_OIDC`, `ARM_CLIENT_ID`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` (or the
  AWS role ARN) live as **variables** on each environment — they are identifiers, not credentials. Scope `ARM_*` to the
  job that needs it, never the workflow.
- **Promotion App credentials:** `PROMOTE_APP_ID` (variable) and `PROMOTE_APP_PRIVATE_KEY` (secret) live on
  `promote-stg` and `promote-prd` only, so only the approved `promote-stg`/`promote-prd` job can mint an
  installation token. The App is the only bypass actor on the `stage`/`main` rulesets.
- **`VERSION_URL`** (variable, per deploy environment): the endpoint that returns `{ sha, env }`; `smoke` polls it.
  Without it, `smoke` records the deployment and warns.
- **Deploy identities in one closed table** (`.github/deploy-identities.yaml`): the plan job asserts its effective client
  id / role is the read-only identity, the apply job asserts it matches the committed writer for that environment.
- The promotion contract this enforces is [branch-promotion](../../core/_shared/branch-promotion.md).
- Alerts as code promote with the pipeline — SigNoz provider in the same root, one state per environment; post-apply
  read-back and ownership rules: [set-up-alerting](../../ops/set-up-alerting/SKILL.md).

## 7. Verify

```bash
actionlint                                                            # syntax and expressions
pipx run zizmor==1.30.1 .github/workflows                             # injection, permissions, unpinned refs
grep -rn "uses:" .github/workflows | grep -vE "@[0-9a-f]{40}|uses: \./"   # expect: no output
```

```bash
pnpm --dir <fleet-standard> fleet check .   # <fleet-standard> = a clone of VelimirMueller/fleet-standard; expect: Result: conforms
```

End to end, in this order:

1. Open a PR → `ci.yml` runs `lint` (Terraform checks and workflow lint, credential-free) and `conclusion`. No plan.
2. Merge → nothing deploys. `gh workflow run deploy.yml --ref develop` → dev plan + apply with no human gate.
3. `gh workflow run promote.yml -f target=stg` → `e2e`, the `promote-stg` approval, `stage` = the `develop` SHA,
   then the stg plan + apply.
4. `gh workflow run promote.yml -f target=prd` → the `promote-prd` approval, a plan that has changes → the
   `tf-apply-prd` gate → apply → smoke test reports the deployed SHA.
5. `branch-sync.yml` is green; `gh workflow run tf-drift.yml` opens no issue (exit 0 per env).

## References
- [workflow-templates.md](./workflow-templates.md): the workflow files, the Terraform root, config and setup script, copy-ready.
- [terraform-pipeline-patterns.md](./terraform-pipeline-patterns.md): why each rule exists, the safety rules, when to deviate.
- [../../core/_shared/branch-promotion.md](../../core/_shared/branch-promotion.md): the promotion contract.
- [../set-up-opentofu/SKILL.md](../set-up-opentofu/SKILL.md): OpenTofu layout, encryption, backend.
- [../_shared/environments.md](../_shared/environments.md), [../_shared/stack-versions.md](../_shared/stack-versions.md).
- [../../ops/set-up-alerting/SKILL.md](../../ops/set-up-alerting/SKILL.md): alerts as code in the same pipeline.
