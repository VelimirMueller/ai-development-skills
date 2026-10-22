---
name: set-up-terraform-pipeline
description: Use when a repo runs Terraform or OpenTofu on GitHub Actions — Azure or AWS via OIDC, develop/stage/main promotion with approval gates, saved plans applied after approval, and weekly drift detection.
---

# Set Up Terraform Pipeline

Infrastructure changes follow the same branch-promotion contract as application code: one plan per
environment, a human approves the plan, `apply` runs only the saved plan — never a re-plan. Contract:
[branch-promotion](../../core/_shared/branch-promotion.md). This skill generates the full pipeline; the
file-by-file content is [workflow-templates.md](./workflow-templates.md), the reasons are
[terraform-pipeline-patterns.md](./terraform-pipeline-patterns.md).

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
  a PR plan that takes the state lock) → apply only the delta; list each fix before editing.
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

`scripts/setup-github.sh` (in [workflow-templates.md](./workflow-templates.md)) creates, idempotently: the nine GitHub
environments (`dev`/`stg`/`prd`, `dev-plan`/`stg-plan`/`prd-plan`, `promote-stg`/`promote-prd`, `tf-apply-prd`), the
required reviewers on every gate environment, the deployment branch policies, the `stage`/`main` rulesets with the
promotion App in the bypass list, and the OIDC subject read-out. Create and install the promotion GitHub App
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
| `.github/workflows/infra.yml` | Entry point. `setup` resolves env from ref, then `check`, `plan`, `gate` (prd only, only if changes), `apply`, `smoke`, `conclusion`. No logic beyond wiring. |
| `.github/workflows/_tf-check.yml` | `fmt -check -recursive`, `validate` every env with `init -backend=false`, tflint, trivy config, `terraform test`, version-pin guard. Credential-free. |
| `.github/workflows/_tf-plan.yml` | OIDC login, `init`, `plan -detailed-exitcode -out tfplan`, destroy/replace guard, summary, upload `tfplan-<env>-<sha>`, PR comment. |
| `.github/workflows/_tf-apply.yml` | Download `tfplan-<env>-<sha>`, verify sha, `apply tfplan`. Binds `environment: <env>`. |
| `.github/workflows/promote.yml` | `preflight` (ff check, `main` contained, previous env green for the SHA, nothing in flight, changelog) → `push` (waits for the `promote-<target>` approval, App token, fast-forward) → `verify`. Targets `stg`, `prd`, `stg-hotfix`. |
| `.github/workflows/branch-sync.yml` | Assert `main ⊆ stage ⊆ develop`; open the back-merge PR or the reconcile issue. |
| `.github/workflows/branch-policy.yml` | Required check: PR into `stage` fails; PR into `main` passes only `hotfix/*`. |
| `.github/workflows/tf-drift.yml` | Weekly read-only plan per env; exit 2 opens one issue per env. |
| `.github/workflows/workflow-lint.yml` | actionlint + zizmor, blocking. |
| `.github/actionlint.yaml`, `.tflint.hcl`, `.github/dependabot.yml` | config |
| `scripts/setup-github.sh` | the step-4 idempotent setup |

Keep the rules from the templates: pin every third-party `uses:` to a full SHA with the version in a trailing comment;
`permissions: {}` at workflow level; `persist-credentials: false` on every checkout; one exact tool version.

## 6. Wire

- **Environment variables, not secrets:** `ARM_USE_OIDC`, `ARM_CLIENT_ID`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` (or the
  AWS role ARN) live as **variables** on each environment — they are identifiers, not credentials. Scope `ARM_*` to the
  job that needs it, never the workflow.
- **Promotion App credentials:** `PROMOTE_APP_ID` (variable) and `PROMOTE_APP_PRIVATE_KEY` (secret) live on
  `promote-stg` and `promote-prd` only, so the
  `push` job can mint an installation token (a `GITHUB_TOKEN` push does not start the deploy pipeline).
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

End to end, in this order:

1. Open a PR → `check` runs (credential-free), plus a dev plan; a sticky comment shows the dev plan.
2. Merge → dev plan + apply with no human gate.
3. Run `promote.yml` with `target: stg` → the `promote-stg` approval, then `stage` = the `develop` SHA, then stg apply.
4. Run `promote.yml` with `target: prd` → the `promote-prd` approval, a plan that has changes → the `tf-apply-prd` gate
   → apply → smoke test reports the deployed SHA.
5. `branch-sync.yml` is green; the weekly `tf-drift.yml` opens no issue (exit 0 or no "changes" issue per env).

## References
- [workflow-templates.md](./workflow-templates.md): the nine workflow files plus config and setup script, copy-ready.
- [terraform-pipeline-patterns.md](./terraform-pipeline-patterns.md): why each rule exists, the safety rules, when to deviate.
- [../../core/_shared/branch-promotion.md](../../core/_shared/branch-promotion.md): the promotion contract.
- [../set-up-opentofu/SKILL.md](../set-up-opentofu/SKILL.md): OpenTofu layout, encryption, backend.
- [../_shared/environments.md](../_shared/environments.md), [../_shared/stack-versions.md](../_shared/stack-versions.md).
- [../../ops/set-up-alerting/SKILL.md](../../ops/set-up-alerting/SKILL.md): alerts as code in the same pipeline.
