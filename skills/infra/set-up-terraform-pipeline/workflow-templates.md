# Workflow Templates

Copy-ready files for [set-up-terraform-pipeline](./SKILL.md). Rules and reasons:
[terraform-pipeline-patterns.md](./terraform-pipeline-patterns.md). Merge strategy they enforce:
[branch-promotion](../../core/_shared/branch-promotion.md).

Status: every workflow below passed `actionlint` 1.7.12 and `zizmor` 1.30.1 (`--offline`, no findings) and
`scripts/setup-github.sh` passed `bash -n` and `shellcheck` on 2026-10-22. None has run on GitHub yet —
treat the first run in a real repo as the test. Pins were resolved from the GitHub API on 2026-10-22.

Fill in before the first run: `cloud: azure|aws` and `tool: terraform|tofu` in `infra.yml` and
`tf-drift.yml`; `.terraform-version` (or `.opentofu-version`) with one exact version; per-environment
variables (`ARM_CLIENT_ID`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` or `AWS_ROLE_ARN`, `AWS_REGION`,
`HEALTH_URL`); `PROMOTE_APP_ID` (variable) and `PROMOTE_APP_PRIVATE_KEY` (secret) on `promote-stg` and
`promote-prd`.

| File | Trigger | Role |
|---|---|---|
| `infra.yml` | PR, push to `develop`/`stage`/`main`, ref-bound dispatch | Entry: `setup` → `check` → `plan` → `gate` (prd, changes only) → `apply` → `smoke` → `conclusion` |
| `_tf-check.yml` | called | fmt, version guard, validate per env, tflint, trivy, test — no credentials |
| `_tf-plan.yml` | called | OIDC, init, `plan -detailed-exitcode`, destroy guard, summary, artifact, PR comment |
| `_tf-apply.yml` | called | applies the saved plan only, serialised per environment |
| `promote.yml` | dispatch `stg` / `prd` / `stg-hotfix` | preflight → `promote-*` approval → fast-forward push (App token) → wait for the target run |
| `branch-sync.yml` | push, daily | asserts `main ⊆ stage ⊆ develop`; opens the back-merge PR or the reconcile issue |
| `branch-policy.yml` | PR into `stage`/`main` | required check: no PR into `stage`; only `hotfix/*` into `main` |
| `tf-drift.yml` | weekly | read-only plan per env; one issue per drifting env |
| `workflow-lint.yml` | PR, push | actionlint + zizmor, blocking |

### `.github/workflows/infra.yml`

Entry workflow: the `setup` job resolves `env`, `mode`, `plan_env` and `lock` from the event (push, pull request, ref-bound dispatch), then wires `check`, `plan`, the prd `gate`, `apply`, `smoke` (records the deployment and polls health until it reports the SHA) and the always-running `conclusion` job — the single required status check.

```yaml
name: Infra

on:
  pull_request:
    branches: [develop, main]
  push:
    branches: [develop, stage, main]
  workflow_dispatch:
    inputs:
      environment:
        description: Environment to plan or apply
        type: choice
        options: [dev, stg, prd]
        required: true
      mode:
        description: plan only, or plan then apply
        type: choice
        options: [plan, apply]
        default: plan
        required: true

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: infra-${{ github.event_name == 'pull_request' && format('pr-{0}', github.event.number) || github.ref_name }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  setup:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    outputs:
      env: ${{ steps.resolve.outputs.env }}
      mode: ${{ steps.resolve.outputs.mode }}
      plan_env: ${{ steps.resolve.outputs.plan_env }}
      lock: ${{ steps.resolve.outputs.lock }}
    steps:
      - name: Resolve environment, mode and lock from the event
        id: resolve
        env:
          EVENT_NAME: ${{ github.event_name }}
          REF_NAME: ${{ github.ref_name }}
          REF: ${{ github.ref }}
          BASE_REF: ${{ github.event.pull_request.base.ref }}
          ENV_INPUT: ${{ inputs.environment }}
          MODE_INPUT: ${{ inputs.mode }}
        run: |
          set -euo pipefail
          case "$EVENT_NAME" in
            push)
              case "$REF_NAME" in
                develop) env=dev ;;
                stage) env=stg ;;
                main) env=prd ;;
                *)
                  echo "::error::push to '$REF_NAME' has no environment; stage and main move only via promote.yml"
                  exit 1
                  ;;
              esac
              mode=apply
              ;;
            pull_request)
              case "$BASE_REF" in
                develop) env=dev ;;
                main) env=prd ;;
                *)
                  echo "::error::pull request into '$BASE_REF' is not wired; target develop (hotfix into main is the only exception)"
                  exit 1
                  ;;
              esac
              mode=plan
              ;;
            workflow_dispatch)
              case "$REF" in
                refs/heads/develop) allowed=dev ;;
                refs/heads/stage) allowed=stg ;;
                refs/heads/main) allowed=prd ;;
                *) allowed= ;;
              esac
              if [ -z "$allowed" ]; then
                echo "::error::dispatch from '$REF' is not allowed (develop@dev, stage@stg, main@prd only)"
                exit 1
              fi
              if [ "$ENV_INPUT" != "$allowed" ]; then
                echo "::error::environment '$ENV_INPUT' does not match '$REF'; expected '$allowed'"
                exit 1
              fi
              case "$MODE_INPUT" in
                plan|apply) mode=$MODE_INPUT ;;
                *)
                  echo "::error::mode must be 'plan' or 'apply', got '$MODE_INPUT'"
                  exit 1
                  ;;
              esac
              env=$allowed
              ;;
            *)
              echo "::error::event '$EVENT_NAME' is not wired"
              exit 1
              ;;
          esac
          if [ "$mode" = "apply" ]; then
            plan_env=$env
            lock=true
          else
            plan_env="${env}-plan"
            lock=false
          fi
          {
            echo "env=$env"
            echo "mode=$mode"
            echo "plan_env=$plan_env"
            echo "lock=$lock"
          } >> "$GITHUB_OUTPUT"
          echo "Resolved: env=$env mode=$mode plan_env=$plan_env lock=$lock"

  check:
    needs: setup
    permissions:
      contents: read
    uses: ./.github/workflows/_tf-check.yml # zizmor: ignore[self-repository] -- actionlint 1.7.12 rejects $/
    with:
      tool: terraform
      working-directory: terraform

  plan:
    needs: [setup, check]
    permissions:          # a called workflow never gets more than its caller grants
      contents: read
      id-token: write
      pull-requests: write
    uses: ./.github/workflows/_tf-plan.yml # zizmor: ignore[self-repository] -- actionlint 1.7.12 rejects $/
    with:
      environment: ${{ needs.setup.outputs.env }}
      plan-environment: ${{ needs.setup.outputs.plan_env }}
      cloud: azure
      tool: terraform
      working-directory: terraform
      lock: ${{ needs.setup.outputs.lock == 'true' }}
      pr-comment: ${{ github.event_name == 'pull_request' }}
      ref: ${{ github.sha }}

  gate:
    needs: [setup, plan]
    if: needs.setup.outputs.env == 'prd' && needs.plan.outputs.has_changes == '2' && needs.setup.outputs.mode == 'apply'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions: {}
    environment: tf-apply-prd
    steps:
      - name: Human approval for the prd apply
        env:
          ENV_NAME: ${{ needs.setup.outputs.env }}
        run: |
          set -euo pipefail
          echo "prd gate approved: the apply for environment '$ENV_NAME' may proceed."

  apply:
    needs: [setup, plan, gate]
    # !cancelled(): without a status function a skipped `gate` (dev, stg) would skip this job too
    if: >-
      !cancelled() &&
      needs.plan.result == 'success' &&
      needs.setup.outputs.mode == 'apply' &&
      needs.plan.outputs.has_changes == '2' &&
      (needs.setup.outputs.env != 'prd' || needs.gate.result == 'success')
    permissions:
      contents: read
      id-token: write
      actions: read
    uses: ./.github/workflows/_tf-apply.yml # zizmor: ignore[self-repository] -- actionlint 1.7.12 rejects $/
    with:
      environment: ${{ needs.setup.outputs.env }}
      cloud: azure
      tool: terraform
      working-directory: terraform
      artifact: ${{ needs.plan.outputs.artifact }}
      ref: ${{ github.sha }}

  smoke:
    needs: [setup, plan, apply]
    if: >-
      !cancelled() &&
      github.event_name != 'pull_request' &&
      needs.setup.outputs.mode == 'apply' &&
      (
        needs.apply.result == 'success' ||
        (needs.plan.result == 'success' && needs.plan.outputs.has_changes == '0')
      )
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions: {}
    environment: ${{ needs.setup.outputs.env }}
    steps:
      - name: Poll the health endpoint until it reports this commit
        env:
          HEALTH_URL: ${{ vars.HEALTH_URL }}
          EXPECTED_SHA: ${{ github.sha }}
          ENV_NAME: ${{ needs.setup.outputs.env }}
        run: |
          set -euo pipefail
          if [ -z "$HEALTH_URL" ]; then
            # infra-only repos: the job still records the deployment of this SHA for promote.yml
            echo "::warning::vars.HEALTH_URL is not set on '$ENV_NAME'; deployment recorded without a health check"
            exit 0
          fi
          deadline=$((SECONDS + 600))
          while [ "$SECONDS" -lt "$deadline" ]; do
            version="$(curl -fsS --max-time 10 "$HEALTH_URL" | jq -r '.version // empty' || true)"
            if [ "$version" = "$EXPECTED_SHA" ]; then
              echo "Healthy: $HEALTH_URL reports version $version"
              exit 0
            fi
            echo "waiting: '$ENV_NAME' reports '${version:-nothing}', expected '$EXPECTED_SHA'"
            sleep 15
          done
          echo "::error::'$ENV_NAME' did not report version '$EXPECTED_SHA' at $HEALTH_URL within 10 minutes"
          exit 1

  conclusion:
    if: always()
    needs: [setup, check, plan, gate, apply, smoke]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    steps:
      - name: Fail when any needed job failed or was cancelled
        env:
          SETUP: ${{ needs.setup.result }}
          CHECK: ${{ needs.check.result }}
          PLAN: ${{ needs.plan.result }}
          GATE: ${{ needs.gate.result }}
          APPLY: ${{ needs.apply.result }}
          SMOKE: ${{ needs.smoke.result }}
        run: |
          set -euo pipefail
          rc=0
          for pair in setup:"$SETUP" check:"$CHECK" plan:"$PLAN" gate:"$GATE" apply:"$APPLY" smoke:"$SMOKE"; do
            name="${pair%%:*}"
            result="${pair#*:}"
            if [ "$result" != "success" ] && [ "$result" != "skipped" ]; then
              echo "::error::job '$name' ended as '$result'"
              rc=1
            fi
          done
          if [ "$rc" -eq 0 ]; then
            echo "All needed jobs succeeded or were skipped as planned."
          fi
          exit "$rc"
```

### `.github/workflows/_tf-check.yml`

Credential-free reusable check workflow (safe for Dependabot runs): `fmt -check -recursive`, a version-pin guard that fails unless the version file, `required_version` and the `tool` input agree on one exact version, a per-env matrix of `init -backend=false` + `validate`, tflint with the repo `.tflint.hcl`, a trivy config scan from a pinned container image, and `terraform test`.

```yaml
name: Terraform check

on:
  workflow_call:
    inputs:
      tool:
        description: CLI to run (terraform or tofu)
        type: string
        required: false
        default: terraform
      working-directory:
        description: Directory that holds the Terraform root module
        type: string
        required: false
        default: terraform

permissions: {}

defaults:
  run:
    shell: bash

jobs:
  version-pin:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    outputs:
      version: ${{ steps.guard.outputs.version }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - name: Enforce one exact version across version file, required_version and tool input
        id: guard
        env:
          TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          case "$TOOL" in
            terraform|tofu) ;;
            *)
              echo "::error::tool input must be 'terraform' or 'tofu', got '$TOOL'"
              exit 1
              ;;
          esac
          if [ "$TOOL" = "terraform" ]; then
            version_file=".terraform-version"
          else
            version_file=".opentofu-version"
          fi
          file=""
          for candidate in "$DIR/$version_file" "$version_file"; do
            if [ -f "$candidate" ]; then
              file=$candidate
              break
            fi
          done
          if [ -z "$file" ]; then
            echo "::error::$version_file not found in '$DIR' or at the repo root"
            exit 1
          fi
          pinned="$(tr -d '[:space:]' < "$file")"
          line="$(grep -h "required_version" "$DIR"/*.tf 2>/dev/null || true)"
          if [ -z "$line" ]; then
            echo "::error::no required_version constraint found in '$DIR'/*.tf"
            exit 1
          fi
          required="$(printf '%s\n' "$line" | grep -oE '"[^"]*"' | head -n 1 | tr -d '"')"
          required="$(printf '%s' "$required" | sed -e 's/^[[:space:]]*=//' -e 's/[[:space:]]//g')"
          if printf '%s' "$required" | grep -qE '[<>~!,]'; then
            echo "::error::required_version '$required' is a range; pin one exact version (\"$pinned\")"
            exit 1
          fi
          if [ "$required" != "$pinned" ]; then
            echo "::error::$file pins '$pinned' but required_version pins '$required'"
            exit 1
          fi
          echo "version=$pinned" >> "$GITHUB_OUTPUT"
          echo "$TOOL $pinned: version file, required_version and tool input agree ($file)."

  fmt:
    needs: version-pin
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        if: inputs.tool == 'terraform'
        with:
          terraform_version: ${{ needs.version-pin.outputs.version }}
          terraform_wrapper: false
      - uses: opentofu/setup-opentofu@a1320f892987e89d278cc92dc5adc984fb93aca4 # v2.0.2
        if: inputs.tool == 'tofu'
        with:
          tofu_version: ${{ needs.version-pin.outputs.version }}
      - name: fmt -check -recursive
        env:
          TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          "$TOOL" -chdir="$DIR" fmt -check -recursive

  validate:
    needs: version-pin
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    strategy:
      fail-fast: false
      matrix:
        env: [dev, stg, prd]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        if: inputs.tool == 'terraform'
        with:
          terraform_version: ${{ needs.version-pin.outputs.version }}
          terraform_wrapper: false
      - uses: opentofu/setup-opentofu@a1320f892987e89d278cc92dc5adc984fb93aca4 # v2.0.2
        if: inputs.tool == 'tofu'
        with:
          tofu_version: ${{ needs.version-pin.outputs.version }}
      - name: "init -backend=false and validate (${{ matrix.env }})"
        env:
          TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
          ENV_NAME: ${{ matrix.env }}
        run: |
          set -euo pipefail
          for f in "$DIR/envs/$ENV_NAME.tfvars" "$DIR/envs/$ENV_NAME.backend.hcl"; do
            if [ ! -f "$f" ]; then
              echo "::error::missing $f"
              exit 1
            fi
          done
          "$TOOL" -chdir="$DIR" init -backend=false -input=false
          "$TOOL" -chdir="$DIR" validate

  tflint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: terraform-linters/setup-tflint@6ffdbaa3be476b3431f7275c26966ef32ff60337 # v6.3.2
        with:
          tflint_version: 0.64.0
      - name: tflint --init
        run: |
          set -euo pipefail
          tflint --init
      - name: tflint --recursive
        run: |
          set -euo pipefail
          tflint --recursive

  trivy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - name: Trivy config scan from the pinned container image
        env:
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          docker run --rm -v "$PWD:/src" aquasec/trivy:0.76.1 config --exit-code 1 --severity HIGH,CRITICAL "/src/$DIR"

  test:
    needs: version-pin
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        if: inputs.tool == 'terraform'
        with:
          terraform_version: ${{ needs.version-pin.outputs.version }}
          terraform_wrapper: false
      - uses: opentofu/setup-opentofu@a1320f892987e89d278cc92dc5adc984fb93aca4 # v2.0.2
        if: inputs.tool == 'tofu'
        with:
          tofu_version: ${{ needs.version-pin.outputs.version }}
      - name: terraform test
        env:
          TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          "$TOOL" -chdir="$DIR" init -backend=false -input=false
          "$TOOL" -chdir="$DIR" test
```

### `.github/workflows/_tf-plan.yml`

Reusable plan workflow: checks out the pinned ref, binds the read-only plan environment (OIDC credentials from environment variables), runs `init -lockfile=readonly` and `plan -detailed-exitcode` (lock optional), counts destroy/replace actions, renders the plan to the step summary truncated at 60000 chars, uploads the saved-plan artifact only when there are changes, and posts a sticky PR comment on demand.

````yaml
name: Terraform plan

on:
  workflow_call:
    inputs:
      environment:
        description: Target Terraform environment (dev, stg or prd)
        type: string
        required: true
      plan-environment:
        description: GitHub environment to bind, e.g. dev-plan or dev
        type: string
        required: true
      cloud:
        description: azure or aws
        type: string
        required: true
      tool:
        description: terraform or tofu
        type: string
        default: terraform
      working-directory:
        description: Terraform root module directory
        type: string
        default: terraform
      lock:
        description: Take the state lock (false for preview and drift plans)
        type: boolean
        default: true
      pr-comment:
        description: Post the plan as a sticky PR comment
        type: boolean
        default: false
      ref:
        description: Commit SHA to check out and plan
        type: string
        required: true
    outputs:
      has_changes:
        description: 0 when the plan is empty, 2 when it has changes
        value: ${{ jobs.plan.outputs.has_changes }}
      destroys:
        description: Number of delete and replace actions in the plan
        value: ${{ jobs.plan.outputs.destroys }}
      artifact:
        description: Artifact name holding the saved plan
        value: ${{ jobs.plan.outputs.artifact }}

permissions: {}

jobs:
  plan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: ${{ inputs.plan-environment }}
    permissions:
      contents: read
      id-token: write       # OIDC token for the cloud login
      pull-requests: write  # sticky plan comment
    defaults:
      run:
        shell: bash
        working-directory: ${{ inputs.working-directory }}
    env:
      TF_IN_AUTOMATION: "true"
      ARM_CLIENT_ID: ${{ vars.ARM_CLIENT_ID }}
      ARM_TENANT_ID: ${{ vars.ARM_TENANT_ID }}
      ARM_SUBSCRIPTION_ID: ${{ vars.ARM_SUBSCRIPTION_ID }}
      ARM_USE_OIDC: "true"
      ARM_USE_AZUREAD: "true"
    outputs:
      has_changes: ${{ steps.plan.outputs.has_changes }}
      destroys: ${{ steps.show.outputs.destroys }}
      artifact: ${{ steps.plan.outputs.artifact }}
    steps:
      - name: Check out the ref to plan
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ inputs.ref }}
          persist-credentials: false

      - name: Read the pinned tool version
        id: version
        working-directory: .
        run: |
          name=.terraform-version
          [ "$TF_TOOL" = "tofu" ] && name=.opentofu-version
          file=""
          # same lookup order as _tf-check.yml: the module directory first, then the repo root
          for candidate in "$DIR/$name" "$name"; do
            [ -s "$candidate" ] && { file=$candidate; break; }
          done
          [ -n "$file" ] || { echo "::error::$name is missing — pin one exact version"; exit 1; }
          echo "version=$(tr -d '[:space:]' < "$file")" >> "$GITHUB_OUTPUT"
        env:
          TF_TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}

      - name: Set up Terraform
        if: inputs.tool == 'terraform'
        uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with:
          terraform_version: ${{ steps.version.outputs.version }}
          terraform_wrapper: false

      - name: Set up OpenTofu
        if: inputs.tool == 'tofu'
        uses: opentofu/setup-opentofu@a1320f892987e89d278cc92dc5adc984fb93aca4 # v2.0.2
        with:
          tofu_version: ${{ steps.version.outputs.version }}
          tofu_wrapper: false

      - name: Resolve the tool binary
        run: |
          if [ "$TF_TOOL" = "tofu" ]; then
            echo "TF_CMD=tofu" >> "$GITHUB_ENV"
          else
            echo "TF_CMD=terraform" >> "$GITHUB_ENV"
          fi
        env:
          TF_TOOL: ${{ inputs.tool }}

      - name: Configure AWS credentials
        if: inputs.cloud == 'aws'
        uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}

      - name: Init
        run: |
          "$TF_CMD" init -backend-config="envs/${ENVIRONMENT}.backend.hcl" -lockfile=readonly -input=false
        env:
          ENVIRONMENT: ${{ inputs.environment }}

      - name: Plan
        id: plan
        run: |
          if [ "$LOCK" = "true" ]; then
            lock_args=(-lock-timeout=5m)
          else
            lock_args=(-lock=false)
          fi
          set +e
          "$TF_CMD" plan -var-file="envs/${ENVIRONMENT}.tfvars" -detailed-exitcode -input=false "${lock_args[@]}" -out=tfplan
          ec=$?
          set -e
          if [ "$ec" -ne 0 ] && [ "$ec" -ne 2 ]; then
            echo "::error::plan failed with exit code $ec"
            exit "$ec"
          fi
          {
            echo "has_changes=$ec"
            echo "artifact=tfplan-${ENVIRONMENT}-${REF}"
          } >> "$GITHUB_OUTPUT"
        env:
          ENVIRONMENT: ${{ inputs.environment }}
          REF: ${{ inputs.ref }}
          LOCK: ${{ inputs.lock }}

      - name: Render plan and count destroys
        id: show
        run: |
          "$TF_CMD" show -json tfplan > plan.json
          "$TF_CMD" show -no-color tfplan > plan.txt
          destroys=$(jq '[(.resource_changes // [])[] | select(.change.actions | index("delete"))] | length' plan.json)
          echo "destroys=$destroys" >> "$GITHUB_OUTPUT"

      - name: Write plan summary
        run: |
          {
            if [ "$DESTROYS" -gt 0 ]; then
              echo "### ⚠ $DESTROYS to destroy/replace"
              echo ""
              jq -r '[(.resource_changes // [])[] | select(.change.actions | index("delete")) | .address] | .[0:20][]' plan.json
              echo ""
            fi
            if [ "$HAS_CHANGES" = "0" ]; then
              echo "No changes."
              echo ""
            fi
            echo '```text'
            if [ "$(wc -c < plan.txt)" -gt 60000 ]; then
              head -c 60000 plan.txt
              echo ""
              echo "… plan truncated at 60000 characters — download the plan artifact for the full plan."
            else
              cat plan.txt
            fi
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
        env:
          DESTROYS: ${{ steps.show.outputs.destroys }}
          HAS_CHANGES: ${{ steps.plan.outputs.has_changes }}

      - name: Upload plan artifact
        if: steps.plan.outputs.has_changes == '2'
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: ${{ steps.plan.outputs.artifact }}
          path: |
            ${{ inputs.working-directory }}/tfplan
            ${{ inputs.working-directory }}/plan.txt
            ${{ inputs.working-directory }}/plan.json
          retention-days: 7
          if-no-files-found: error

      - name: Build the PR comment (GitHub limits a comment to 65536 characters)
        if: inputs.pr-comment && github.event_name == 'pull_request'
        run: |
          {
            echo "#### Terraform plan — \`$ENVIRONMENT\` — $DESTROYS to destroy/replace"
            echo '```text'
            head -c 60000 plan.txt
            echo '```'
          } > plan-comment.md
        env:
          ENVIRONMENT: ${{ inputs.environment }}
          DESTROYS: ${{ steps.show.outputs.destroys }}

      - name: Comment the plan on the PR
        if: inputs.pr-comment && github.event_name == 'pull_request'
        uses: marocchino/sticky-pull-request-comment@5770ad5eb8f42dd2c4f34da00c94c5381e49af88 # v3.0.5
        with:
          header: tfplan-${{ inputs.environment }}
          path: ${{ inputs.working-directory }}/plan-comment.md
````

### `.github/workflows/_tf-apply.yml`

Reusable apply workflow: binds the target environment, serializes per environment with cancel-in-progress false, downloads the saved plan for the exact SHA, verifies tfplan and plan.txt, re-inits the backend read-only, applies only the saved plan, and fails with a clear annotation when the plan is stale.

````yaml
name: Terraform apply

on:
  workflow_call:
    inputs:
      environment:
        description: Target environment to apply (dev, stg or prd)
        type: string
        required: true
      cloud:
        description: azure or aws
        type: string
        required: true
      tool:
        description: terraform or tofu
        type: string
        default: terraform
      working-directory:
        description: Terraform root module directory
        type: string
        default: terraform
      artifact:
        description: Plan artifact name (tfplan-<env>-<sha>)
        type: string
        required: true
      ref:
        description: Commit SHA the plan was made for
        type: string
        required: true

permissions: {}

jobs:
  apply:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    environment: ${{ inputs.environment }}
    concurrency:
      group: tf-apply-${{ inputs.environment }}
      cancel-in-progress: false
    permissions:
      contents: read
      id-token: write       # OIDC token for the cloud login
      actions: read         # download the plan artifact
    defaults:
      run:
        shell: bash
        working-directory: ${{ inputs.working-directory }}
    env:
      TF_IN_AUTOMATION: "true"
      ARM_CLIENT_ID: ${{ vars.ARM_CLIENT_ID }}
      ARM_TENANT_ID: ${{ vars.ARM_TENANT_ID }}
      ARM_SUBSCRIPTION_ID: ${{ vars.ARM_SUBSCRIPTION_ID }}
      ARM_USE_OIDC: "true"
      ARM_USE_AZUREAD: "true"
    steps:
      - name: Check out the ref to apply
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ inputs.ref }}
          persist-credentials: false

      - name: Download the saved plan
        uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: ${{ inputs.artifact }}
          path: ${{ inputs.working-directory }}

      - name: Verify the saved plan
        run: |
          if [ ! -s tfplan ]; then
            echo "::error::tfplan is missing or empty — run the plan job again"
            exit 1
          fi
          if [ ! -s plan.txt ]; then
            echo "::error::plan.txt is missing or empty — run the plan job again"
            exit 1
          fi

      - name: Read the pinned tool version
        id: version
        working-directory: .
        run: |
          name=.terraform-version
          [ "$TF_TOOL" = "tofu" ] && name=.opentofu-version
          file=""
          # same lookup order as _tf-check.yml: the module directory first, then the repo root
          for candidate in "$DIR/$name" "$name"; do
            [ -s "$candidate" ] && { file=$candidate; break; }
          done
          [ -n "$file" ] || { echo "::error::$name is missing — pin one exact version"; exit 1; }
          echo "version=$(tr -d '[:space:]' < "$file")" >> "$GITHUB_OUTPUT"
        env:
          TF_TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}

      - name: Set up Terraform
        if: inputs.tool == 'terraform'
        uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with:
          terraform_version: ${{ steps.version.outputs.version }}
          terraform_wrapper: false

      - name: Set up OpenTofu
        if: inputs.tool == 'tofu'
        uses: opentofu/setup-opentofu@a1320f892987e89d278cc92dc5adc984fb93aca4 # v2.0.2
        with:
          tofu_version: ${{ steps.version.outputs.version }}
          tofu_wrapper: false

      - name: Resolve the tool binary
        run: |
          if [ "$TF_TOOL" = "tofu" ]; then
            echo "TF_CMD=tofu" >> "$GITHUB_ENV"
          else
            echo "TF_CMD=terraform" >> "$GITHUB_ENV"
          fi
        env:
          TF_TOOL: ${{ inputs.tool }}

      - name: Configure AWS credentials
        if: inputs.cloud == 'aws'
        uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}

      - name: Init
        run: |
          "$TF_CMD" init -backend-config="envs/${ENVIRONMENT}.backend.hcl" -lockfile=readonly -input=false
        env:
          ENVIRONMENT: ${{ inputs.environment }}

      - name: Apply the saved plan
        run: |
          set +e
          "$TF_CMD" apply -input=false -lock-timeout=5m tfplan > apply.log 2>&1
          ec=$?
          set -e
          cat apply.log
          if grep -q "Saved plan is stale" apply.log; then
            echo "::error::Stale plan — start a new run, do not re-run this job"
            exit 1
          fi
          exit "$ec"
````

### `.github/workflows/promote.yml`

The only way `stage` and `main` move: resolves the source SHA once, proves the fast-forward and the previous environment's green deployment, waits for the `promote-<target>` approval, pushes that exact SHA with an App token (so the push starts `infra.yml`), then waits for the target pipeline run of that SHA.

```yaml
name: Promote

on:
  workflow_dispatch:
    inputs:
      target:
        description: stg = develop → stage · prd = stage → main · stg-hotfix = main → stage after a hotfix
        type: choice
        options: [stg, prd, stg-hotfix]
        required: true

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: promote-${{ inputs.target }}
  cancel-in-progress: false

jobs:
  preflight:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      actions: read
      deployments: read
    outputs:
      sha: ${{ steps.resolve.outputs.sha }}
      branch: ${{ steps.resolve.outputs.branch }}
      gate: ${{ steps.resolve.outputs.gate }}
      nothing_to_do: ${{ steps.resolve.outputs.nothing_to_do }}
    steps:
      - name: Refuse a dispatch from any ref but the default branch
        env:
          REF: ${{ github.ref }}
        run: |
          # The workflow file is read from the dispatched ref; only develop's copy is trusted.
          if [ "$REF" != "refs/heads/develop" ]; then
            echo "::error::run promote.yml from develop (got $REF)"
            exit 1
          fi

      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Resolve the SHA once and check every precondition
        id: resolve
        env:
          TARGET: ${{ inputs.target }}
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          case "$TARGET" in
            stg)        source=develop; branch=stage; prev_env=dev; gate=promote-stg ;;
            prd)        source=stage;   branch=main;  prev_env=stg; gate=promote-prd ;;
            stg-hotfix) source=main;    branch=stage; prev_env=prd; gate=promote-stg ;;
            *) echo "::error::unknown target '$TARGET'"; exit 1 ;;
          esac
          # fetch-depth: 0 already loaded every origin/* ref; a second fetch would need credentials
          sha=$(git rev-parse "origin/$source")

          # Whatever moves must already contain main — otherwise a prd hotfix would be dropped.
          if ! git merge-base --is-ancestor origin/main "$sha"; then
            echo "::error::$source@$sha does not contain main — back-merge main first (branch-sync opens the PR)"
            exit 1
          fi
          if [ "$(git rev-parse "origin/$branch")" = "$sha" ]; then
            echo "::notice::$branch already is $source ($sha) — nothing to promote"
            { echo "sha=$sha"; echo "branch=$branch"; echo "gate=$gate"; echo "nothing_to_do=true"; } >> "$GITHUB_OUTPUT"
            exit 0
          fi
          if ! git merge-base --is-ancestor "origin/$branch" "$sha"; then
            echo "::error::$branch is not an ancestor of $source@$sha — a fast-forward is impossible"
            exit 1
          fi

          # The SHA must have deployed green on the previous environment.
          dep_id=$(gh api "repos/$REPO/deployments?environment=$prev_env&sha=$sha" --jq '.[0].id // empty')
          state=none
          if [ -n "$dep_id" ]; then
            state=$(gh api "repos/$REPO/deployments/$dep_id/statuses" --jq '.[0].state // "none"')
          fi
          if [ "$state" != "success" ]; then
            echo "::error::$sha has no successful deployment on $prev_env (latest: $state)"
            exit 1
          fi

          # Nothing may be in flight on the target branch (a waiting run blocks the env queue).
          busy=$(gh run list --repo "$REPO" --workflow infra.yml --branch "$branch" --limit 20 \
            --json status --jq '[.[] | select(.status != "completed")] | length')
          if [ "$busy" != "0" ]; then
            echo "::error::$busy infra.yml run(s) on $branch are not completed — finish or reject them first"
            exit 1
          fi

          {
            echo "### Promote \`$source\` → \`$branch\` ($TARGET)"
            echo ""
            echo "SHA: \`$sha\` · deployed green on \`$prev_env\`"
            echo ""
            echo '```text'
            git log --oneline "origin/$branch..$sha"
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
          { echo "sha=$sha"; echo "branch=$branch"; echo "gate=$gate"; echo "nothing_to_do=false"; } >> "$GITHUB_OUTPUT"

  push:
    needs: preflight
    if: needs.preflight.outputs.nothing_to_do != 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    # The approval gate: one approval per promotion. Only this job can read the App credentials.
    environment: ${{ needs.preflight.outputs.gate }}
    steps:
      - name: Mint an App token (a GITHUB_TOKEN push would not start infra.yml)
        id: app
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          app-id: ${{ vars.PROMOTE_APP_ID }}
          private-key: ${{ secrets.PROMOTE_APP_PRIVATE_KEY }}
          repositories: ${{ github.event.repository.name }}
          permission-contents: write   # the token can push commits, nothing else

      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Fast-forward the target branch to the approved SHA
        env:
          SHA: ${{ needs.preflight.outputs.sha }}
          BRANCH: ${{ needs.preflight.outputs.branch }}
          APP_TOKEN: ${{ steps.app.outputs.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          git remote set-url origin "https://x-access-token:${APP_TOKEN}@github.com/${REPO}.git"
          git fetch --quiet origin "$BRANCH"
          # Re-check: the branch may have moved during the approval wait.
          if ! git merge-base --is-ancestor "origin/$BRANCH" "$SHA"; then
            echo "::error::$BRANCH moved and is no longer an ancestor of $SHA — start a new promotion"
            exit 1
          fi
          # No --force: git refuses anything that is not a fast-forward.
          git push origin "$SHA:refs/heads/$BRANCH"
          echo "::notice::$BRANCH := $SHA"

  verify:
    needs: [preflight, push]
    runs-on: ubuntu-latest
    timeout-minutes: 45
    permissions:
      actions: read
    steps:
      - name: Wait for the target pipeline run of this SHA
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
          SHA: ${{ needs.preflight.outputs.sha }}
          BRANCH: ${{ needs.preflight.outputs.branch }}
        run: |
          set -euo pipefail
          deadline=$((SECONDS + 1800))
          while [ "$SECONDS" -lt "$deadline" ]; do
            run=$(gh run list --repo "$REPO" --workflow infra.yml --branch "$BRANCH" --commit "$SHA" \
              --limit 1 --json databaseId,status,conclusion,url --jq '.[0] // empty')
            if [ -n "$run" ]; then
              status=$(jq -r .status <<<"$run")
              conclusion=$(jq -r .conclusion <<<"$run")
              url=$(jq -r .url <<<"$run")
              if [ "$status" = "completed" ]; then
                echo "infra.yml on $BRANCH: $conclusion — $url" >> "$GITHUB_STEP_SUMMARY"
                [ "$conclusion" = "success" ] && exit 0
                echo "::error::target pipeline ended '$conclusion': $url"
                exit 1
              fi
              # 'waiting' = parked at tf-apply-prd: a person must approve the plan in that run.
              echo "infra.yml on $BRANCH is $status — $url"
            else
              echo "no infra.yml run for $SHA on $BRANCH yet"
            fi
            sleep 30
          done
          echo "::error::no completed infra.yml run for $SHA on $BRANCH within 30 minutes"
          exit 1
```

### `.github/workflows/branch-sync.yml`

Watches `develop`/`stage`/`main` on every push and daily, verifies the `main ⊆ stage ⊆ develop` ancestry invariant, and opens a reconcile issue (lineage gap) or a back-merge PR (content) when `main` carries commits `develop` lacks.

```yaml
name: branch-sync

on:
  push:
    branches: [develop, stage, main]
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:

permissions: {}

defaults:
  run:
    shell: bash

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write
      pull-requests: write
      issues: write
    steps:
      - name: Checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Inspect branch chain
        id: inspect
        env:
          MAIN: origin/main
          STAGE: origin/stage
          DEVELOP: origin/develop
        run: |
          set -euo pipefail
          main="$MAIN"
          stage="$STAGE"
          develop="$DEVELOP"

          main_ahead=0
          git merge-base --is-ancestor "$main" "$develop" || main_ahead=1

          if [ "$main_ahead" = 0 ]; then
            reason=""
            if ! git merge-base --is-ancestor "$main" "$stage" && git merge-base --is-ancestor "$stage" "$main"; then
              # the normal state right after a hotfix on main: stage only needs to catch up
              echo "mode=stage-behind" >> "$GITHUB_OUTPUT"
              exit 0
            fi
            git merge-base --is-ancestor "$main" "$stage" || reason="main is not an ancestor of stage"
            if [ -z "$reason" ]; then
              git merge-base --is-ancestor "$stage" "$develop" || reason="stage is not an ancestor of develop"
            fi
            if [ -n "$reason" ]; then
              echo "reason=$reason" >> "$GITHUB_OUTPUT"
              echo "mode=broken" >> "$GITHUB_OUTPUT"
              exit 0
            fi
            echo "mode=ok" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          mb="$(git merge-base "$main" "$develop")"
          echo "main_sha=$(git rev-parse "$main")" >> "$GITHUB_OUTPUT"
          echo "mb=$mb" >> "$GITHUB_OUTPUT"
          if git diff --quiet "$mb" "$main"; then
            echo "mode=issue" >> "$GITHUB_OUTPUT"
          else
            echo "mode=pr" >> "$GITHUB_OUTPUT"
          fi

      - name: Open lineage-gap issue
        if: steps.inspect.outputs.mode == 'issue'
        uses: actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0
        with:
          script: |
            const title = 'branch-sync: lineage gap (reconcile needed)';
            const body = [
              'The branch chain has a lineage-only gap: `main` and `develop` have identical content but `main` is not an ancestor of `develop`.',
              '',
              '## Reconcile (content-free, lineage-only)',
              '',
              '~~~bash',
              'MB=$(git merge-base origin/main origin/develop)',
              'git diff --stat "$MB" origin/main   # must be empty',
              `MERGE=\$(git commit-tree 'origin/develop^{tree}' -p origin/develop -p origin/main -m "chore(promote): reconcile develop lineage with main")`,
              'git diff --stat origin/develop "$MERGE"   # must be empty',
              'git merge-base --is-ancestor origin/main "$MERGE"   # must succeed',
              '# then push $MERGE to develop via a PR',
              '~~~',
              '',
              '> **Warning:** never use the `commit-tree` recipe when the content discriminator is non-empty — it silently reverts the hotfix and every check still passes.',
            ].join('\n');
            const { data: issues } = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'open',
            });
            const existing = issues.find((i) => i.title === title && !i.pull_request);
            if (existing) {
              await github.rest.issues.update({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: existing.number,
                body,
              });
              core.info(`Updated issue #${existing.number}`);
            } else {
              const created = await github.rest.issues.create({
                owner: context.repo.owner,
                repo: context.repo.repo,
                title,
                body,
              });
              core.info(`Opened issue #${created.data.number}`);
            }

      - name: Open back-merge PR
        if: steps.inspect.outputs.mode == 'pr'
        uses: actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0
        env:
          MAIN_SHA: ${{ steps.inspect.outputs.main_sha }}
        with:
          script: |
            const owner = context.repo.owner;
            const repo = context.repo.repo;
            const branch = 'sync/main-into-develop';
            const mainSha = process.env.MAIN_SHA;
            const ref = `heads/${branch}`;
            const { data: open } = await github.rest.pulls.list({ owner, repo, state: 'open', head: `${owner}:${branch}` });
            if (open.length > 0) {
              // never reset a branch a person may be resolving conflicts on
              core.info(`Back-merge PR #${open[0].number} already open`);
              return;
            }
            try {
              await github.rest.git.getRef({ owner, repo, ref });
              await github.rest.git.updateRef({ owner, repo, ref, sha: mainSha, force: true });
              core.info(`Updated branch ${branch} to ${mainSha}`);
            } catch (error) {
              if (error.status === 404) {
                await github.rest.git.createRef({ owner, repo, ref: `refs/heads/${branch}`, sha: mainSha });
                core.info(`Created branch ${branch} at ${mainSha}`);
              } else {
                throw error;
              }
            }
            const { data: pulls } = await github.rest.pulls.list({
              owner,
              repo,
              state: 'open',
              head: `${owner}:${branch}`,
            });
            if (pulls.length > 0) {
              core.info(`Back-merge PR #${pulls[0].number} already open`);
              return;
            }
            await github.rest.pulls.create({
              owner,
              repo,
              title: 'chore(sync): back-merge main into develop',
              head: branch,
              base: 'develop',
              body: 'Merge with a **merge commit**, never squash.',
            });
            core.info('Opened back-merge PR');

      - name: Fail on broken chain
        if: steps.inspect.outputs.mode == 'broken'
        env:
          REASON: ${{ steps.inspect.outputs.reason }}
        run: |
          set -euo pipefail
          echo "::error::$REASON"
          echo "Commands to inspect:"
          echo "  git rev-list --count origin/stage..origin/main    # must be 0"
          echo "  git rev-list --count origin/develop..origin/stage  # must be 0"
          echo "  git log --oneline --decorate --graph --all"
          exit 1

      - name: Fail while stage is behind main
        if: steps.inspect.outputs.mode == 'stage-behind'
        run: |
          echo "::error::stage is behind main after a hotfix — run: gh workflow run promote.yml -f target=stg-hotfix"
          exit 1

      - name: Fail on sync gap
        if: steps.inspect.outputs.mode == 'issue' || steps.inspect.outputs.mode == 'pr'
        env:
          MODE: ${{ steps.inspect.outputs.mode }}
        run: |
          set -euo pipefail
          if [ "$MODE" = 'issue' ]; then
            echo "::error::lineage gap: main and develop have identical content but main is not an ancestor of develop (issue opened with the reconcile recipe)"
          else
            echo "::error::main has content develop lacks (back-merge PR opened)"
          fi
          exit 1
```

### `.github/workflows/branch-policy.yml`

Required status check for PRs into `stage` and `main`: rejects every PR into `stage` and allows only `hotfix/*` heads into `main`.

```yaml
name: branch-policy

on:
  pull_request:
    branches: [stage, main]

permissions: {}

defaults:
  run:
    shell: bash

jobs:
  branch-policy:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Enforce promotion policy
        env:
          BASE_REF: ${{ github.base_ref }}
          HEAD_REF: ${{ github.head_ref }}
        run: |
          set -euo pipefail
          if [ "$BASE_REF" = 'stage' ]; then
            echo "::error::stage moves only by promote.yml — PRs into stage are never allowed"
            exit 1
          fi
          if [ "$BASE_REF" = 'main' ]; then
            case "$HEAD_REF" in
              hotfix/*)
                echo "PR into main from hotfix branch is allowed"
                ;;
              *)
                echo "::error::PRs into main are allowed only from hotfix/* branches"
                exit 1
                ;;
            esac
          fi
```

### `.github/workflows/tf-drift.yml`

Weekly drift check that plans `dev`/`stg`/`prd` against live state and opens or closes one `drift: <env>` issue per environment.

```yaml
name: tf-drift

on:
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

permissions: {}

defaults:
  run:
    shell: bash

jobs:
  # Scheduled legs bind <env>-plan only. A gated environment (tf-apply-prd, promote-*)
  # would wait for a reviewer that never comes in a schedule, so never bind it here.
  plan-dev:
    name: plan (dev)
    permissions:          # a called workflow never gets more than its caller grants
      contents: read
      id-token: write
      pull-requests: write  # declared by _tf-plan.yml's job; unused without pr-comment
    uses: ./.github/workflows/_tf-plan.yml  # zizmor: ignore[self-repository]
    with:
      environment: dev
      plan-environment: dev-plan
      cloud: azure
      lock: false
      pr-comment: false
      ref: ${{ github.sha }}

  plan-stg:
    name: plan (stg)
    permissions:          # a called workflow never gets more than its caller grants
      contents: read
      id-token: write
      pull-requests: write  # declared by _tf-plan.yml's job; unused without pr-comment
    uses: ./.github/workflows/_tf-plan.yml  # zizmor: ignore[self-repository]
    with:
      environment: stg
      plan-environment: stg-plan
      cloud: azure
      lock: false
      pr-comment: false
      ref: ${{ github.sha }}

  plan-prd:
    name: plan (prd)
    permissions:          # a called workflow never gets more than its caller grants
      contents: read
      id-token: write
      pull-requests: write  # declared by _tf-plan.yml's job; unused without pr-comment
    uses: ./.github/workflows/_tf-plan.yml  # zizmor: ignore[self-repository]
    with:
      environment: prd
      plan-environment: prd-plan
      cloud: azure
      lock: false
      pr-comment: false
      ref: ${{ github.sha }}

  report:
    name: report (${{ matrix.env }})
    needs:
      - plan-dev
      - plan-stg
      - plan-prd
    if: ${{ !cancelled() }}
    strategy:
      fail-fast: false
      matrix:
        env:
          - dev
          - stg
          - prd
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      issues: write
    env:
      DEV_HAS_CHANGES: ${{ needs.plan-dev.outputs.has_changes }}
      STG_HAS_CHANGES: ${{ needs.plan-stg.outputs.has_changes }}
      PRD_HAS_CHANGES: ${{ needs.plan-prd.outputs.has_changes }}
    steps:
      - name: Reconcile drift issue
        uses: actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0
        env:
          DRIFT_ENV: ${{ matrix.env }}
        with:
          script: |
            const targetEnv = process.env.DRIFT_ENV
            const hasChanges = process.env[targetEnv.toUpperCase() + "_HAS_CHANGES"]
            const title = "drift: " + targetEnv
            const label = "tf-drift"

            const { data: issues } = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: "all",
              labels: label,
              per_page: 100,
            })
            const existing = issues.find((i) => i.title === title && !i.pull_request)

            if (hasChanges === "2") {
              const body =
                "Terraform drift detected for environment `" + targetEnv + "`.\n\n" +
                "The scheduled plan shows changes against the deployed state. " +
                "Review and reconcile before the next promotion."
              if (existing) {
                await github.rest.issues.update({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  issue_number: existing.number,
                  state: "open",
                  body,
                })
              } else {
                await github.rest.issues.create({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  title,
                  body,
                  labels: [label],
                })
              }
            } else if (hasChanges === "0") {
              if (existing && existing.state === "open") {
                await github.rest.issues.update({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  issue_number: existing.number,
                  state: "closed",
                })
              }
            }
```

### `.github/workflows/workflow-lint.yml`

CI gate that runs a checksum-verified actionlint download and the pinned zizmor action over the workflows.

```yaml
name: workflow-lint

on:
  pull_request:
  push:

permissions: {}

defaults:
  run:
    shell: bash

jobs:
  actionlint:
    name: actionlint
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Install actionlint
        env:
          ACTIONLINT_VERSION: "1.7.12"
        run: |
          set -euo pipefail
          tarball="actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"
          curl -fsSL -o "/tmp/${tarball}" "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/${tarball}"
          curl -fsSL -o /tmp/actionlint_checksums.txt "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_checksums.txt"
          expected="$(grep -F " ${tarball}" /tmp/actionlint_checksums.txt | awk '{print $1}')"
          actual="$(sha256sum "/tmp/${tarball}" | awk '{print $1}')"
          if [ -z "${expected}" ] || [ "${expected}" != "${actual}" ]; then
            echo "::error::actionlint ${ACTIONLINT_VERSION} checksum mismatch (expected ${expected}, got ${actual})"
            exit 1
          fi
          tar -xzf "/tmp/${tarball}" -C /tmp actionlint
          sudo install -m 0755 /tmp/actionlint /usr/local/bin/actionlint
          actionlint -version

      - name: Lint workflows
        run: actionlint

  zizmor:
    name: zizmor
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Lint workflows
        uses: zizmorcore/zizmor-action@cc914d7f3750a2d13d75c7f184a1060aa0e9d482 # v0.6.4
        with:
          persona: regular
          advanced-security: "false"
```

### `.github/actionlint.yaml`

actionlint config: lists self-hosted runner labels (none by default) so a new label is a reviewed change.

```yaml
# Add a label here before any workflow uses `runs-on: <self-hosted label>`.
self-hosted-runner:
  labels: []
```

### `.tflint.hcl`

tflint config: keep the plugin of your cloud and delete the other block.

```hcl
plugin "azurerm" {
  enabled = true
  version = "0.32.0" # latest release on 2026-10-22; Dependabot does not bump tflint plugins
  source  = "github.com/terraform-linters/tflint-ruleset-azurerm"
}

plugin "aws" {
  enabled = true
  version = "0.49.0" # latest release on 2026-10-22
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
```

### `.github/dependabot.yml`

Dependabot config with weekly, grouped updates for GitHub Actions and Terraform and a 7-day cooldown.

```yaml
version: 2

updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      actions:
        patterns:
          - "*"

  - package-ecosystem: terraform
    directory: /terraform
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      terraform:
        patterns:
          - "*"
```

### `terraform/backend.tf`

Backend block presenting both the azurerm and s3 state backend variants.

```hcl
# Azure — azurerm state backend (the default for this setup).
terraform {
  backend "azurerm" {}
}

# AWS — s3 backend; use this block instead and delete the azurerm block.
# terraform {
#   backend "s3" {}
# }
```

### `terraform/envs/dev.backend.hcl`

Per-environment backend config for `dev`, with the azurerm and s3 variants side by side.

```hcl
# Azure — azurerm backend.
resource_group_name  = "rg-<app>-tfstate"
storage_account_name = "st<app>devtfstate"   # one storage account per environment
container_name       = "tfstate"
key                  = "<app>-dev.tfstate"
use_azuread_auth     = true
use_oidc             = true

# AWS — s3 backend; use these keys instead and delete the azurerm keys.
# bucket       = "<app>-dev-tfstate"           # one bucket per environment (or per account)
# key          = "<app>/dev.tfstate"
# region       = "eu-central-1"
# use_lockfile = true
# encrypt      = true
```

### `scripts/setup-github.sh`

Idempotent bootstrap of the GitHub side of the pipeline: creates the nine environments (`dev`/`stg`/`prd` deploy envs with deployment branch policies `develop`/`stage`/`main`, the `*-plan` plan envs, and the `promote-stg`, `promote-prd`, `tf-apply-prd` gates with team reviewers), upserts the `promotion: stage` and `promotion: main` rulesets with the promotion App as the only bypass actor, asserts every gate has required reviewers, and prints the repo's OIDC subject template.

```bash
#!/usr/bin/env bash
# setup-github.sh - idempotent GitHub bootstrap for the branch-promotion
# pipeline: the nine environments (deploy, plan, approval gates) with their
# deployment branch policies, and the promotion rulesets on stage and main.
#
# Usage: setup-github.sh <owner/repo> <reviewer-team-slug> <app-id>
#   <app-id> is the numeric id of the promotion GitHub App (the bypass actor).

set -euo pipefail

usage() {
  echo "usage: $0 <owner/repo> <reviewer-team-slug> <app-id>" >&2
  exit 2
}

(($# == 3)) || usage

REPO="$1"
TEAM_SLUG="$2"
APP_ID="$3"
ORG="${REPO%%/*}"

command -v gh >/dev/null 2>&1 || {
  echo "::error:: gh is required" >&2
  exit 1
}

[[ "${APP_ID}" =~ ^[0-9]+$ ]] || {
  echo "::error:: <app-id> must be the numeric id of the promotion App" >&2
  exit 2
}

# ------------------------------------------------------------------- team --

TEAM_ID="$(gh api "orgs/${ORG}/teams/${TEAM_SLUG}" --jq .id)"
[[ "${TEAM_ID}" =~ ^[0-9]+$ ]] || {
  echo "::error:: could not resolve team '${TEAM_SLUG}' in org '${ORG}'" >&2
  exit 1
}
echo "reviewer team '${TEAM_SLUG}': id ${TEAM_ID}"

# ------------------------------------------------------------ environments --

# env_put <name> - create or update an environment; JSON body on stdin.
env_put() {
  gh api -X PUT "repos/${REPO}/environments/$1" --input - >/dev/null
}

# deploy env: no reviewers; custom deployment branch policy (added below).
env_deploy() {
  env_put "$1" <<'JSON'
{
  "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}
}
JSON
}

# plan env: no reviewers, no branch policy.
env_plan() {
  env_put "$1" <<'JSON'
{"deployment_branch_policy": null}
JSON
}

# gate env: team reviewers; prevent_self_review per argument (true|false).
env_gate() {
  env_put "$1" <<JSON
{
  "reviewers": [{"type": "Team", "id": ${TEAM_ID}}],
  "prevent_self_review": $2
}
JSON
}

# branch_policy <env> <branch> - add the custom branch policy; idempotent.
branch_policy() {
  local env_name="$1" branch="$2" out=""
  if out="$(gh api -X POST "repos/${REPO}/environments/${env_name}/deployment-branch-policies" -f "name=${branch}" 2>&1)"; then
    echo "  ${env_name}: branch policy '${branch}'"
  elif grep -q "already exists" <<<"${out}"; then
    echo "  ${env_name}: branch policy '${branch}' (already set)"
  else
    echo "::error:: ${env_name}: cannot set branch policy '${branch}': ${out}" >&2
    exit 1
  fi
}

echo "== environments =="

# Deploy environments: no reviewers (deploy credentials only); one branch each.
env_deploy dev
branch_policy dev develop
env_deploy stg
branch_policy stg stage
env_deploy prd
branch_policy prd main

# Plan environments: read-only plan credentials; no reviewers, no branch policy.
env_plan dev-plan
env_plan stg-plan
env_plan prd-plan

# Gate environments: an environment without reviewers never waits.
env_gate promote-stg false
env_gate promote-prd true
env_gate tf-apply-prd true

# ---------------------------------------------------------------- rulesets --

# ruleset_json <branch> - full ruleset body on stdout.
ruleset_json() {
  cat <<JSON
{
  "name": "promotion: $1",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/heads/$1"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {"required_approving_review_count": 1, "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": true, "require_last_push_approval": true,
      "required_review_thread_resolution": true, "allowed_merge_methods": ["merge"]}},
    {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": false,
      "required_status_checks": [{"context": "branch-policy"}]}}
  ],
  "bypass_actors": [{"actor_id": ${APP_ID}, "actor_type": "Integration", "bypass_mode": "always"}]
}
JSON
}

# upsert_ruleset <branch> - create or update, looked up by name.
upsert_ruleset() {
  local branch="$1" name="promotion: $1" id
  id="$(gh api "repos/${REPO}/rulesets" --paginate \
    --jq ".[] | select(.name == \"${name}\") | .id" | head -n 1 || true)"
  if [[ -n "${id}" ]]; then
    ruleset_json "${branch}" | gh api -X PUT "repos/${REPO}/rulesets/${id}" --input - >/dev/null
    echo "ruleset '${name}' updated (id ${id})"
  else
    ruleset_json "${branch}" | gh api -X POST "repos/${REPO}/rulesets" --input - >/dev/null
    echo "ruleset '${name}' created"
  fi
}

echo "== rulesets =="
upsert_ruleset stage
upsert_ruleset main

# -------------------------------------------------------------- assertions --

echo "== assertions =="
for gate in promote-stg promote-prd tf-apply-prd; do
  count="$(gh api "repos/${REPO}/environments/${gate}" \
    --jq '[.protection_rules[]|select(.type=="required_reviewers")]|length')"
  if ((count < 1)); then
    echo "::error:: gate environment '${gate}' has no required reviewers" >&2
    exit 1
  fi
  echo "  ${gate}: required reviewers present"
done

# -------------------------------------------------------------------- OIDC --

echo "OIDC subject template (for cloud OIDC federations):"
gh api "repos/${REPO}/actions/oidc/customization/sub" || echo "  (no custom template - default claims)"
```

