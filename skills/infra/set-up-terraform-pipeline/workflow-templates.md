# Workflow Templates

Copy-ready files for [set-up-terraform-pipeline](./SKILL.md). Rules and reasons:
[terraform-pipeline-patterns.md](./terraform-pipeline-patterns.md). Merge strategy they enforce:
[branch-promotion](../../core/_shared/branch-promotion.md). The files follow the fleet standard
(`VelimirMueller/fleet-standard`: `STANDARD.md`, `docs/standard/`); rule IDs in the text (`WF-*`, `CI-*`,
`CI-COST-*`, `GOV-*`, `TF-*`) point there.

Status: on 2026-10-23 a repo rendered from these files (tier `deploys`, visibility `public`) passed `fleet check`
with no exception record. Pins were resolved from the GitHub API on 2026-10-22 (`dorny/paths-filter` on
2026-10-23). None of the workflows has run on GitHub yet; treat the first run in a real repo as the test. `VelimirMueller/fleet-workflows` has no `v1` tag yet (2026-10-23): until it does, the `unit`, `e2e` and `build` calls do not resolve.

Fill in before the first run: `cloud: azure|aws|none` and `tool: terraform|tofu` in `infra.yml`, `tf-drift.yml` and
`_ci-lint.yml`; `terraform/.terraform-version` (or `.opentofu-version`) with one exact version; per-environment variables (`ARM_CLIENT_ID`, `ARM_TENANT_ID`,
`ARM_SUBSCRIPTION_ID` or `AWS_ROLE_ARN`, `AWS_REGION`, `VERSION_URL`); `PROMOTE_APP_ID` (variable) and
`PROMOTE_APP_PRIVATE_KEY` (secret) on `promote-stg` and `promote-prd`.

Every deploy starts by hand (`workflow_dispatch`, CI-COST-01): a merge or a push deploys nothing, also not to `dev`.

| File | Trigger | Role |
|---|---|---|
| `ci.yml` | PR into `develop`/`main`, dispatch | `changes` → `lint` (workflow lint + Terraform checks) → `unit` → `e2e` (dispatch only) → `build` → `conclusion` |
| `_ci-lint.yml` | called | actionlint + zizmor, and `_tf-check.yml`; credential-free |
| `infra.yml` | dispatch, ref-bound | `setup` → `plan` → `gate` (prd, changes only) → `apply` → `smoke` → `tf-conclusion` |
| `_tf-check.yml` | called | version guard, fmt, validate per env, test, tflint, trivy — one job, no credentials |
| `_tf-plan.yml` | called | OIDC, init, `plan -detailed-exitcode`, destroy guard, summary, artifact |
| `_tf-apply.yml` | called | applies the saved plan only, serialised per environment |
| `deploy.yml` | dispatch on `develop` | `setup` (ref and green-check guard) → `deploy-dev` (starts `infra.yml` for `dev`, waits) |
| `promote.yml` | dispatch `stg` / `prd` / `stg-hotfix` | `setup` → `preflight` → `e2e` (stg) → `promote-*` (approval, fast-forward with App token, deploy and wait) |
| `branch-sync.yml` | push to `develop`/`stage`/`main`, dispatch | asserts `main ⊆ stage ⊆ develop`; opens the back-merge PR or the reconcile issue |
| `branch-policy.yml` | PR into `stage`/`main` | required check: no PR into `stage`; only `hotfix/*` into `main` |
| `tf-drift.yml` | dispatch | read-only plan per env; one issue per drifting env |
| `tf-apply-prd.yml` | dispatch | `private-free` repos only: apply a saved prd plan (GOV-PRV-02) |

### `.github/workflows/ci.yml`

The one PR check workflow (stages 1 to 4). `changes` decides what runs, so the required `conclusion` check always
reports (CI-COST-10); `lint` runs the workflow lint when `.github/workflows/**` changed (CI-LINT-03) and the Terraform
static checks when `*.tf`, `*.tfvars` or the lock file changed (CI-LINT-04). `unit`, `e2e` and `build` are the app
stages from the fleet reusable workflows; an app repo adds its language lint to `_ci-lint.yml`. `e2e` runs only by
`workflow_dispatch` with `e2e: true` (CI-E2E-01). The callers pin `VelimirMueller/fleet-workflows` at `@v1`.

```yaml
name: ci

on:
  pull_request:
    branches: [develop, main]
    types: [opened, synchronize, reopened, ready_for_review]
  workflow_dispatch:
    inputs:
      e2e:
        description: Run the e2e stage
        type: boolean
        default: false

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: ci-${{ github.event.number || github.ref }}
  cancel-in-progress: true

jobs:
  changes:
    if: ${{ !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
      pull-requests: read
    outputs:
      code: ${{ github.event_name != 'pull_request' || steps.filter.outputs.code == 'true' }}
      terraform: ${{ github.event_name != 'pull_request' || steps.filter.outputs.terraform == 'true' }}
      workflows: ${{ github.event_name != 'pull_request' || steps.filter.outputs.workflows == 'true' }}
    steps:
      - name: Detect code changes
        id: filter
        if: github.event_name == 'pull_request'
        uses: dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d # v4.0.3
        with:
          # every: a file counts only when it matches all patterns of a filter, so the negations combine
          predicate-quantifier: every
          filters: |
            code:
              - '!**/*.md'
              - '!docs/**'
              - '!LICENSE'
              - '!.github/ISSUE_TEMPLATE/**'
            terraform:
              - '**/{*.tf,*.tfvars,.terraform.lock.hcl}'
            workflows:
              - '.github/workflows/**'

  lint:
    needs: changes
    if: ${{ !failure() && !cancelled() && needs.changes.outputs.code == 'true' }}
    permissions:
      contents: read
    uses: ./.github/workflows/_ci-lint.yml # zizmor: ignore[self-repository] -- actionlint 1.7.12 rejects $/
    with:
      terraform: ${{ needs.changes.outputs.terraform == 'true' }}
      workflow-lint: ${{ needs.changes.outputs.workflows == 'true' }}

  unit:
    needs: [changes, lint]
    if: ${{ !failure() && !cancelled() && needs.changes.outputs.code == 'true' }}
    permissions:
      contents: read
    uses: VelimirMueller/fleet-workflows/.github/workflows/_ci-unit.yml@v1
    with:
      stack: node # node|bun|go|python|rust|generic; generic also needs command

  e2e:
    needs: [changes, unit]
    if: ${{ !failure() && !cancelled() && github.event_name == 'workflow_dispatch' && inputs.e2e }}
    permissions:
      contents: read
    uses: VelimirMueller/fleet-workflows/.github/workflows/_ci-e2e.yml@v1
    with:
      stack: node # node|bun|go|python|rust|generic; generic also needs command

  build:
    needs: [changes, e2e]
    if: ${{ !failure() && !cancelled() && needs.changes.outputs.code == 'true' }}
    permissions:
      contents: read
    uses: VelimirMueller/fleet-workflows/.github/workflows/_ci-build.yml@v1 # verify only; publishing is _build-publish.yml
    with:
      stack: node # node|bun|go|python|rust|generic; generic also needs command

  conclusion:
    needs: [changes, lint, unit, e2e, build]
    if: always()
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    steps:
      - name: Fail when a job failed or a required stage was skipped
        env:
          CHANGES: ${{ needs.changes.result }}
          DRAFT: ${{ github.event.pull_request.draft || false }}
          CODE: ${{ needs.changes.outputs.code }}
          RESULTS: ${{ join(needs.*.result, ' ') }}
          LINT: ${{ needs.lint.result }}
          UNIT: ${{ needs.unit.result }}
          BUILD: ${{ needs.build.result }}
          E2E: ${{ needs.e2e.result }}
          E2E_ASKED: ${{ github.event_name == 'workflow_dispatch' && inputs.e2e }}
        run: |
          # changes is skipped only on a draft PR; then nothing else ran and the check passes
          case "$CHANGES" in
            success) ;;
            skipped) [ "$DRAFT" = "true" ] || { echo "::error::changes was skipped"; exit 1; } ;;
            *) echo "::error::changes ended as $CHANGES"; exit 1 ;;
          esac
          for r in $RESULTS; do
            case "$r" in success|skipped) ;; *) echo "::error::a job ended as $r"; exit 1 ;; esac
          done
          if [ "$CODE" = "true" ]; then
            for r in "$LINT" "$UNIT" "$BUILD"; do
              [ "$r" = "success" ] || { echo "::error::a required stage did not run"; exit 1; }
            done
          fi
          if [ "$E2E_ASKED" = "true" ] && [ "$E2E" != "success" ]; then
            echo "::error::e2e was asked for and ended as $E2E"; exit 1
          fi
```

### `.github/workflows/_ci-lint.yml`

The `lint` stage, called by `ci.yml`. Credential-free (CI-LINT-05): `workflow-lint` runs a checksum-verified
actionlint download and the pinned zizmor action, both blocking; `terraform` calls `_tf-check.yml`. A job whose
input is false is skipped, and a skipped job counts as passed.

```yaml
name: ci-lint

on:
  workflow_call:
    inputs:
      terraform:
        description: Run the Terraform static checks
        type: boolean
        default: true
      workflow-lint:
        description: Run actionlint and zizmor
        type: boolean
        default: true

permissions: {}

defaults:
  run:
    shell: bash

jobs:
  workflow-lint:
    if: inputs.workflow-lint
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - name: Check out the code
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
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

      - name: Lint the workflows with actionlint
        run: actionlint

      - name: Lint the workflows with zizmor
        uses: zizmorcore/zizmor-action@cc914d7f3750a2d13d75c7f184a1060aa0e9d482 # v0.6.4
        with:
          persona: regular
          advanced-security: "false"

  terraform:
    if: inputs.terraform
    permissions:
      contents: read
    uses: ./.github/workflows/_tf-check.yml # zizmor: ignore[self-repository] -- actionlint 1.7.12 rejects $/
    with:
      tool: terraform
      working-directory: terraform
```

### `.github/workflows/infra.yml`

Entry workflow, started by hand only (CI-COST-01): run it from `develop` for `dev`, from `stage` for `stg`, from
`main` for `prd`. `setup` resolves `env`, `mode`, `plan_env` and `lock` from the ref and fails on any other pair;
then `plan`, the prd `gate` (only when the plan has changes), `apply`, `smoke` (records the deployment and polls the
version endpoint until it reports this SHA) and the always-running `tf-conclusion` job. The Terraform static checks
run in the `lint` stage of `ci.yml`, not here.

```yaml
name: infra
run-name: infra · ${{ github.ref == 'refs/heads/main' && 'prd' || github.ref == 'refs/heads/stage' && 'stg' || 'dev' }} · ${{ inputs.mode }} · ${{ github.sha }}

on:
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
  group: infra-${{ inputs.environment }}
  cancel-in-progress: false

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
      - name: Resolve environment, mode and lock from the ref
        id: resolve
        env:
          REF: ${{ github.ref }}
          ENV_INPUT: ${{ inputs.environment }}
          MODE_INPUT: ${{ inputs.mode }}
        run: |
          set -euo pipefail
          case "$REF" in
            refs/heads/develop) env=dev ;;
            refs/heads/stage) env=stg ;;
            refs/heads/main) env=prd ;;
            *)
              echo "::error::dispatch from '$REF' is not allowed (develop@dev, stage@stg, main@prd only)"
              exit 1
              ;;
          esac
          if [ "$ENV_INPUT" != "$env" ]; then
            echo "::error::environment '$ENV_INPUT' does not match '$REF'; expected '$env'"
            exit 1
          fi
          case "$MODE_INPUT" in
            plan|apply) mode=$MODE_INPUT ;;
            *)
              echo "::error::mode must be 'plan' or 'apply', got '$MODE_INPUT'"
              exit 1
              ;;
          esac
          if [ "$mode" = "apply" ]; then
            plan_env=$env       # the apply identity plans and holds the state lock
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

  plan:
    needs: setup
    if: github.event_name == 'workflow_dispatch'
    permissions:          # a called workflow never gets more than its caller grants
      contents: read
      id-token: write
    uses: ./.github/workflows/_tf-plan.yml # zizmor: ignore[self-repository] -- actionlint 1.7.12 rejects $/
    with:
      environment: ${{ needs.setup.outputs.env }}
      plan-environment: ${{ needs.setup.outputs.plan_env }}
      cloud: azure
      tool: terraform
      working-directory: terraform
      lock: ${{ needs.setup.outputs.lock == 'true' }}
      ref: ${{ github.sha }}

  gate:
    # exitcode is the plan exit code: 0 no changes, 2 changes (1 fails the plan job), so a missing value gates
    needs: [setup, plan]
    if: needs.setup.outputs.env == 'prd' && needs.setup.outputs.mode == 'apply' && needs.plan.outputs.exitcode != '0'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions: {}
    environment: tf-apply-prd
    steps:
      - name: Record the prd approval
        run: echo "prd apply approved"

  apply:
    needs: [setup, plan, gate]
    # !cancelled(): without a status function a skipped `gate` (dev, stg) would skip this job too
    if: >-
      !cancelled() &&
      github.event_name == 'workflow_dispatch' &&
      needs.plan.result == 'success' &&
      needs.setup.outputs.mode == 'apply' &&
      needs.plan.outputs.exitcode == '2' &&
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
      github.event_name == 'workflow_dispatch' &&
      needs.setup.outputs.mode == 'apply' &&
      (
        needs.apply.result == 'success' ||
        (needs.plan.result == 'success' && needs.plan.outputs.exitcode == '0')
      )
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions: {}
    environment: ${{ needs.setup.outputs.env }}
    steps:
      - name: Poll the version endpoint until it reports this commit
        env:
          VERSION_URL: ${{ vars.VERSION_URL }}
          EXPECTED_SHA: ${{ github.sha }}
          ENV_NAME: ${{ needs.setup.outputs.env }}
        run: |
          set -euo pipefail
          if [ -z "$VERSION_URL" ]; then
            # infra-only repos: the job still records the deployment of this SHA for promote.yml
            echo "::warning::vars.VERSION_URL is not set on '$ENV_NAME'; deployment recorded without a smoke test"
            exit 0
          fi
          deadline=$((SECONDS + 600))
          while [ "$SECONDS" -lt "$deadline" ]; do
            body="$(curl -fsS --max-time 10 "$VERSION_URL" || true)"
            sha="$(jq -r '.sha // empty' <<<"$body" 2>/dev/null || true)"
            env="$(jq -r '.env // empty' <<<"$body" 2>/dev/null || true)"
            if [ "$sha" = "$EXPECTED_SHA" ] && [ "$env" = "$ENV_NAME" ]; then
              echo "Healthy: $VERSION_URL reports $env@$sha"
              exit 0
            fi
            echo "waiting: '$VERSION_URL' reports '${env:-?}@${sha:-?}', expected '$ENV_NAME@$EXPECTED_SHA'"
            sleep 15
          done
          echo "::error::'$ENV_NAME' did not report '$EXPECTED_SHA' at $VERSION_URL within 10 minutes"
          exit 1

  tf-conclusion:
    needs: [setup, plan, gate, apply, smoke]
    if: always()
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    steps:
      - name: Fail when any needed job failed or was cancelled
        env:
          RESULTS: ${{ join(needs.*.result, ' ') }}
        run: |
          for r in $RESULTS; do
            case "$r" in success|skipped) ;; *) echo "::error::a job ended as $r"; exit 1 ;; esac
          done
          echo "All needed jobs succeeded or were skipped as planned."
```

### `.github/workflows/_tf-check.yml`

Credential-free reusable check (safe for Dependabot runs), called by the `lint` stage of `ci.yml`. One job, so one
billed minute instead of six: a version-pin guard (the version file, `required_version` and the `tool` input agree on
one exact version), `fmt -check -recursive`, `init -backend=false` + `validate` for every env, `test`, tflint with
the repo `.tflint.hcl`, and a trivy config scan from a pinned container image.

```yaml
name: tf-check

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
  tf-check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
    steps:
      - name: Check out the code
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
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
            terraform) version_file=.terraform-version ;;
            tofu) version_file=.opentofu-version ;;
            *)
              echo "::error::tool input must be 'terraform' or 'tofu', got '$TOOL'"
              exit 1
              ;;
          esac
          file="$DIR/$version_file"
          if [ ! -s "$file" ]; then
            echo "::error::$file not found; pin one exact version there"
            exit 1
          fi
          pinned="$(tr -d '[:space:]' < "$file")"
          line="$(grep -h "required_version" "$DIR/versions.tf" 2>/dev/null || true)"
          if [ -z "$line" ]; then
            echo "::error::no required_version in '$DIR/versions.tf'"
            exit 1
          fi
          required="$(printf '%s\n' "$line" | grep -oE '"[^"]*"' | head -n 1 | tr -d '"')"
          required="$(printf '%s' "$required" | sed -e 's/^[[:space:]]*=//' -e 's/[[:space:]]//g')"
          if printf '%s' "$required" | grep -qE '[<>~!,]'; then
            echo "::error::required_version '$required' is a range; pin one exact version (\"= $pinned\")"
            exit 1
          fi
          if [ "$required" != "$pinned" ]; then
            echo "::error::$file pins '$pinned' but required_version pins '$required'"
            exit 1
          fi
          echo "version=$pinned" >> "$GITHUB_OUTPUT"
          echo "$TOOL $pinned: version file, required_version and tool input agree ($file)."

      - name: Set up Terraform
        if: inputs.tool == 'terraform'
        uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with:
          terraform_version: ${{ steps.guard.outputs.version }}
          terraform_wrapper: false

      - name: Set up OpenTofu
        if: inputs.tool == 'tofu'
        uses: opentofu/setup-opentofu@a1320f892987e89d278cc92dc5adc984fb93aca4 # v2.0.2
        with:
          tofu_version: ${{ steps.guard.outputs.version }}
          tofu_wrapper: false

      - name: Check the format
        env:
          TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          "$TOOL" -chdir="$DIR" fmt -check -recursive

      - name: Validate every environment without a backend
        env:
          TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          for env in dev stg prd; do
            for f in "$DIR/envs/$env.tfvars" "$DIR/envs/$env.backend.hcl"; do
              if [ ! -f "$f" ]; then
                echo "::error::missing $f"
                exit 1
              fi
            done
          done
          "$TOOL" -chdir="$DIR" init -backend=false -input=false -lockfile=readonly
          "$TOOL" -chdir="$DIR" validate

      - name: Run the root and module tests
        env:
          TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          "$TOOL" -chdir="$DIR" test
          for m in "$DIR"/modules/*/; do
            [ -d "${m}tests" ] || continue
            "$TOOL" -chdir="$m" init -backend=false -input=false
            "$TOOL" -chdir="$m" test
          done

      - name: Set up tflint
        uses: terraform-linters/setup-tflint@6ffdbaa3be476b3431f7275c26966ef32ff60337 # v6.3.2
        with:
          tflint_version: 0.64.0

      - name: Run tflint
        run: |
          set -euo pipefail
          tflint --init
          tflint --recursive

      - name: Scan the configuration with trivy from the pinned container image
        env:
          DIR: ${{ inputs.working-directory }}
        run: |
          set -euo pipefail
          docker run --rm -v "$PWD:/src:ro" aquasec/trivy:0.76.1 config --exit-code 1 --severity HIGH,CRITICAL --no-progress "/src/$DIR"
```

### `.github/workflows/_tf-plan.yml`

Reusable plan workflow: checks out the pinned ref, binds the plan environment (OIDC credentials from environment
variables), runs `init -lockfile=readonly` and `plan -detailed-exitcode` (lock optional), counts destroy/replace
actions, renders the plan to the step summary truncated at 60000 chars, and uploads the saved plan as
`tfplan-<env>-<sha>` only when there are changes. There is no PR plan: a plan with a cloud login is a deploy job
(CI-COST-01), so it runs only from `infra.yml` and `tf-drift.yml`.

````yaml
name: tf-plan

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
        description: azure, aws, or none (static tokens from the environment, e.g. Hetzner)
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
      ref:
        description: Commit SHA to check out and plan
        type: string
        required: true
    outputs:
      exitcode:
        description: Plan exit code, 0 when the plan is empty, 2 when it has changes
        value: ${{ jobs.plan.outputs.exitcode }}
      destroys:
        description: Number of delete and replace actions in the plan
        value: ${{ jobs.plan.outputs.destroys }}
      artifact:
        description: Artifact name holding the saved plan
        value: ${{ jobs.plan.outputs.artifact }}

permissions: {}

defaults:
  run:
    shell: bash

jobs:
  plan:
    # github.event_name is the caller's event here; a copied trigger never plans with credentials
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      id-token: write       # OIDC token for the cloud login
    environment: ${{ inputs.plan-environment }}
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
      exitcode: ${{ steps.plan.outputs.exitcode }}
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
        env:
          TF_TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        working-directory: .
        run: |
          name=.terraform-version
          [ "$TF_TOOL" = "tofu" ] && name=.opentofu-version
          # same file as _tf-check.yml: terraform/.terraform-version (TF-LAYOUT-06)
          [ -s "$DIR/$name" ] || { echo "::error::$DIR/$name is missing; pin one exact version"; exit 1; }
          echo "version=$(tr -d '[:space:]' < "$DIR/$name")" >> "$GITHUB_OUTPUT"

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
        env:
          TF_TOOL: ${{ inputs.tool }}
        run: |
          if [ "$TF_TOOL" = "tofu" ]; then
            echo "TF_CMD=tofu" >> "$GITHUB_ENV"
          else
            echo "TF_CMD=terraform" >> "$GITHUB_ENV"
          fi

      - name: Configure AWS credentials
        if: inputs.cloud == 'aws'
        uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}

      - name: Initialise the backend
        env:
          ENVIRONMENT: ${{ inputs.environment }}
        run: |
          "$TF_CMD" init -backend-config="envs/${ENVIRONMENT}.backend.hcl" -lockfile=readonly -input=false

      - name: Plan
        id: plan
        env:
          ENVIRONMENT: ${{ inputs.environment }}
          REF: ${{ inputs.ref }}
          LOCK: ${{ inputs.lock }}
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
            echo "exitcode=$ec"
            echo "artifact=tfplan-${ENVIRONMENT}-${REF}"
          } >> "$GITHUB_OUTPUT"

      - name: Render the plan and count destroys
        id: show
        run: |
          "$TF_CMD" show -json tfplan > plan.json
          "$TF_CMD" show -no-color tfplan > plan.txt
          destroys=$(jq '[(.resource_changes // [])[] | select(.change.actions | index("delete"))] | length' plan.json)
          echo "destroys=$destroys" >> "$GITHUB_OUTPUT"

      - name: Write the plan summary
        env:
          DESTROYS: ${{ steps.show.outputs.destroys }}
          EXITCODE: ${{ steps.plan.outputs.exitcode }}
        run: |
          {
            if [ "$DESTROYS" -gt 0 ]; then
              echo "### ⚠ $DESTROYS to destroy/replace"
              echo ""
              jq -r '[(.resource_changes // [])[] | select(.change.actions | index("delete")) | .address] | .[0:20][]' plan.json
              echo ""
            fi
            if [ "$EXITCODE" = "0" ]; then
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

      - name: Upload the plan artifact
        if: steps.plan.outputs.exitcode == '2'
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: ${{ steps.plan.outputs.artifact }}
          path: |
            ${{ inputs.working-directory }}/tfplan
            ${{ inputs.working-directory }}/plan.txt
            ${{ inputs.working-directory }}/plan.json
          retention-days: 7
          if-no-files-found: error
````

### `.github/workflows/_tf-apply.yml`

Reusable apply workflow: binds the target environment, serialises per environment with `cancel-in-progress: false`,
downloads the saved plan for the exact SHA, verifies `tfplan` and `plan.txt`, re-inits the backend read-only, applies
only the saved plan, and fails with a clear annotation when the plan is stale.

````yaml
name: tf-apply

on:
  workflow_call:
    inputs:
      environment:
        description: Target environment to apply (dev, stg or prd)
        type: string
        required: true
      cloud:
        description: azure, aws, or none (static tokens from the environment, e.g. Hetzner)
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

defaults:
  run:
    shell: bash

jobs:
  apply:
    # github.event_name is the caller's event here; a copied trigger never applies
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      id-token: write       # OIDC token for the cloud login
      actions: read         # download the plan artifact
    environment: ${{ inputs.environment }}
    concurrency:
      group: tf-apply-${{ inputs.environment }}
      cancel-in-progress: false
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
        env:
          TF_TOOL: ${{ inputs.tool }}
          DIR: ${{ inputs.working-directory }}
        working-directory: .
        run: |
          name=.terraform-version
          [ "$TF_TOOL" = "tofu" ] && name=.opentofu-version
          [ -s "$DIR/$name" ] || { echo "::error::$DIR/$name is missing; pin one exact version"; exit 1; }
          echo "version=$(tr -d '[:space:]' < "$DIR/$name")" >> "$GITHUB_OUTPUT"

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
        env:
          TF_TOOL: ${{ inputs.tool }}
        run: |
          if [ "$TF_TOOL" = "tofu" ]; then
            echo "TF_CMD=tofu" >> "$GITHUB_ENV"
          else
            echo "TF_CMD=terraform" >> "$GITHUB_ENV"
          fi

      - name: Configure AWS credentials
        if: inputs.cloud == 'aws'
        uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}

      - name: Initialise the backend
        env:
          ENVIRONMENT: ${{ inputs.environment }}
        run: |
          "$TF_CMD" init -backend-config="envs/${ENVIRONMENT}.backend.hcl" -lockfile=readonly -input=false

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

### `.github/workflows/deploy.yml`

The `dev` deploy, started by hand on `develop` (CI-DEPLOY-01): a merge into `develop` deploys nothing. `setup`
refuses any other ref and any SHA whose PR checks did not pass (`conclusion` = success on the PR head with the same
tree, CI-DEPLOY-02); `deploy-dev` starts `infra.yml` for `dev` and waits for it. An app repo adds its `build` job
(publish the artifact tagged with the SHA) between the two.

```yaml
name: deploy
run-name: deploy · dev · ${{ github.sha }}

on:
  workflow_dispatch:

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: deploy-deploy-dev
  cancel-in-progress: false

jobs:
  setup:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
      checks: read
      pull-requests: read
    outputs:
      env: ${{ steps.resolve.outputs.env }}
    steps:
      - name: Refuse any ref but develop and any SHA without green PR checks
        id: resolve
        env:
          REF: ${{ github.ref }}
          SHA: ${{ github.sha }}
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          if [ "$REF" != "refs/heads/develop" ]; then
            echo "::error::deploy.yml deploys dev from develop only (got $REF)"
            exit 1
          fi
          # The merge commit is not the PR head; with strict up-to-date PRs both have the same tree.
          head=$(gh api "repos/$REPO/commits/$SHA/pulls" --jq '[.[] | select(.merged_at != null)][0].head.sha // empty')
          if [ -z "$head" ]; then
            echo "::error::$SHA belongs to no merged PR; only reviewed changes deploy"
            exit 1
          fi
          tree_sha=$(gh api "repos/$REPO/git/commits/$SHA" --jq .tree.sha)
          tree_head=$(gh api "repos/$REPO/git/commits/$head" --jq .tree.sha)
          if [ "$tree_sha" != "$tree_head" ]; then
            echo "::error::$SHA and its PR head $head differ in content; the checks did not cover this tree"
            exit 1
          fi
          # the aggregate job of ci.yml is named conclusion; it is the one required check
          ok=$(gh api "repos/$REPO/commits/$head/check-runs?check_name=conclusion" \
            --jq '[.check_runs[] | select(.conclusion == "success")] | length')
          if [ "$ok" = "0" ]; then
            echo "::error::the conclusion check of PR head $head is not green"
            exit 1
          fi
          echo "env=dev" >> "$GITHUB_OUTPUT"

  deploy-dev:
    needs: setup
    if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      actions: write        # dispatch infra.yml on develop
    environment: dev
    steps:
      - name: Check out the code
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Deploy dev and wait for the result
        env:
          SHA: ${{ github.sha }}
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: bash scripts/deploy-env.sh develop dev "$SHA"
```

### `.github/workflows/promote.yml`

The only way `stage` and `main` move, and the only way `stg` and `prd` deploy (CI-PROMOTE-01). Run it from
`develop`. `setup` resolves the target environment once; `preflight` resolves the SHA once and proves the
fast-forward, `main ⊆ stage ⊆ develop`, the previous environment's green deployment and that nothing is in flight;
`e2e` runs against that SHA before any approval (stg only); `promote-stg` or `promote-prd` waits for its approval,
pushes that exact SHA with an App token, then starts `infra.yml` on the target branch and waits for its result. A
merged hotfix (`main` already ahead of `stage`) skips the fast-forward and deploys `main` behind the `promote-prd`
approval (CI-PROMOTE-05).

```yaml
name: promote
run-name: promote · ${{ inputs.target == 'prd' && 'prd' || 'stg' }} · ${{ github.sha }}

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
  setup:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    outputs:
      env: ${{ steps.resolve.outputs.env }}
      source: ${{ steps.resolve.outputs.source }}
      branch: ${{ steps.resolve.outputs.branch }}
      prev_env: ${{ steps.resolve.outputs.prev_env }}
    steps:
      - name: Resolve the target environment from the input
        id: resolve
        env:
          REF: ${{ github.ref }}
          TARGET: ${{ inputs.target }}
        run: |
          set -euo pipefail
          # The workflow file is read from the dispatched ref; only develop's copy is trusted.
          if [ "$REF" != "refs/heads/develop" ]; then
            echo "::error::run promote.yml from develop (got $REF)"
            exit 1
          fi
          case "$TARGET" in
            stg)        env=stg; source=develop; branch=stage; prev_env=dev ;;
            prd)        env=prd; source=stage;   branch=main;  prev_env=stg ;;
            stg-hotfix) env=stg; source=main;    branch=stage; prev_env=prd ;;
            *) echo "::error::unknown target '$TARGET'"; exit 1 ;;
          esac
          {
            echo "env=$env"
            echo "source=$source"
            echo "branch=$branch"
            echo "prev_env=$prev_env"
          } >> "$GITHUB_OUTPUT"

  preflight:
    needs: setup
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      actions: read
      deployments: read
    outputs:
      sha: ${{ steps.check.outputs.sha }}
      fast_forward: ${{ steps.check.outputs.fast_forward }}
    steps:
      - name: Check out every branch
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Resolve the SHA once and check every precondition
        id: check
        env:
          TARGET: ${{ inputs.target }}
          SOURCE: ${{ needs.setup.outputs.source }}
          BRANCH: ${{ needs.setup.outputs.branch }}
          PREV_ENV: ${{ needs.setup.outputs.prev_env }}
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          # fetch-depth: 0 already loaded every origin/* ref; a second fetch would need credentials
          sha=$(git rev-parse "origin/$SOURCE")
          current=$(git rev-parse "origin/$BRANCH")
          fast_forward=true
          hotfix=false

          if [ "$TARGET" = "prd" ] && [ "$sha" != "$current" ] && git merge-base --is-ancestor "$sha" "$current"; then
            # main is ahead of stage: a merged hotfix. Deploy main as it is; no fast-forward (CI-PROMOTE-05).
            sha=$current
            fast_forward=false
            hotfix=true
          elif [ "$sha" = "$current" ]; then
            echo "::notice::$BRANCH already is $SOURCE ($sha); deploy without a fast-forward"
            fast_forward=false
          elif [ "$TARGET" = "stg-hotfix" ]; then
            # stage catches up with a merged hotfix: main is ahead of stage until this push, and the
            # hotfix PR into main was the review, so the invariant and previous-env checks do not apply.
            if ! git merge-base --is-ancestor "$current" "$sha"; then
              echo "::error::stage is not an ancestor of main@$sha; a fast-forward is impossible"
              exit 1
            fi
            hotfix=true
          else
            # Whatever moves must already contain main, or a prd hotfix would be dropped.
            if ! git merge-base --is-ancestor origin/main "$sha"; then
              echo "::error::$SOURCE@$sha does not contain main; back-merge main first (branch-sync opens the PR)"
              exit 1
            fi
            if ! git merge-base --is-ancestor "$current" "$sha"; then
              echo "::error::$BRANCH is not an ancestor of $SOURCE@$sha; a fast-forward is impossible"
              exit 1
            fi
          fi

          # The invariant main ⊆ stage ⊆ develop must hold before anything moves.
          if [ "$hotfix" = "false" ]; then
            git merge-base --is-ancestor origin/main origin/stage || { echo "::error::main is not in stage"; exit 1; }
          fi
          if [ "$TARGET" != "stg-hotfix" ]; then
            git merge-base --is-ancestor origin/stage origin/develop || { echo "::error::stage is not in develop"; exit 1; }
          fi

          # The SHA must have deployed green on the previous environment (a hotfix never ran on stg).
          if [ "$hotfix" = "false" ]; then
            dep_id=$(gh api "repos/$REPO/deployments?environment=$PREV_ENV&sha=$sha" --jq '.[0].id // empty')
            state=none
            if [ -n "$dep_id" ]; then
              state=$(gh api "repos/$REPO/deployments/$dep_id/statuses" --jq '.[0].state // "none"')
            fi
            if [ "$state" != "success" ]; then
              echo "::error::$sha has no successful deployment on $PREV_ENV (latest: $state)"
              exit 1
            fi
          fi

          # Nothing may be in flight on the target branch (a waiting run blocks the env queue).
          busy=$(gh run list --repo "$REPO" --workflow infra.yml --branch "$BRANCH" --limit 20 \
            --json status --jq '[.[] | select(.status != "completed")] | length')
          if [ "$busy" != "0" ]; then
            echo "::error::$busy infra.yml run(s) on $BRANCH are not completed; finish or reject them first"
            exit 1
          fi

          {
            echo "### Promote \`$SOURCE\` → \`$BRANCH\` ($TARGET)"
            echo ""
            echo "SHA: \`$sha\` · fast-forward: $fast_forward · hotfix: $hotfix"
            echo ""
            echo '```text'
            git log --oneline "$current..$sha"
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
          { echo "sha=$sha"; echo "fast_forward=$fast_forward"; } >> "$GITHUB_OUTPUT"

  e2e:
    needs: [setup, preflight]
    if: needs.setup.outputs.env == 'stg'
    permissions:
      contents: read
    uses: VelimirMueller/fleet-workflows/.github/workflows/_ci-e2e.yml@v1
    with:
      stack: node # node|bun|go|python|rust|generic; generic also needs command
      ref: ${{ needs.preflight.outputs.sha }}

  promote-stg:
    needs: [setup, preflight, e2e]
    if: >-
      !cancelled() &&
      github.event_name == 'workflow_dispatch' &&
      needs.setup.outputs.env == 'stg' &&
      needs.preflight.result == 'success' &&
      needs.e2e.result == 'success'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      actions: write        # dispatch infra.yml on the target branch
    # The approval: one per promotion. Only a job bound to this environment can read the App key.
    environment: promote-stg
    steps:
      - name: Mint an App token for the fast-forward push
        id: app
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          app-id: ${{ vars.PROMOTE_APP_ID }}
          private-key: ${{ secrets.PROMOTE_APP_PRIVATE_KEY }}
          repositories: ${{ github.event.repository.name }}
          permission-contents: write   # the token can push commits, nothing else

      - name: Check out every branch
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Push the approved SHA to stage as a fast-forward
        if: needs.preflight.outputs.fast_forward == 'true'
        env:
          SHA: ${{ needs.preflight.outputs.sha }}
          APP_TOKEN: ${{ steps.app.outputs.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          git remote set-url origin "https://x-access-token:${APP_TOKEN}@github.com/${REPO}.git"
          git fetch --quiet origin stage main
          # Re-check: the branches may have moved during the approval wait.
          if ! git merge-base --is-ancestor origin/stage "$SHA"; then
            echo "::error::stage moved and is no longer an ancestor of $SHA; start a new promotion"
            exit 1
          fi
          if ! git merge-base --is-ancestor origin/main "$SHA"; then
            echo "::error::main moved (a hotfix?) and is not in $SHA; back-merge main, then start a new promotion"
            exit 1
          fi
          # No --force: git refuses anything that is not a fast-forward.
          git push origin "$SHA:refs/heads/stage"
          echo "::notice::stage := $SHA"

      - name: Deploy stg and wait for the result
        env:
          SHA: ${{ needs.preflight.outputs.sha }}
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: bash scripts/deploy-env.sh stage stg "$SHA"

  promote-prd:
    needs: [setup, preflight]
    if: >-
      !cancelled() &&
      github.event_name == 'workflow_dispatch' &&
      needs.setup.outputs.env == 'prd' &&
      needs.preflight.result == 'success'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      actions: write        # dispatch infra.yml on the target branch
    environment: promote-prd
    steps:
      - name: Mint an App token for the fast-forward push
        id: app
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          app-id: ${{ vars.PROMOTE_APP_ID }}
          private-key: ${{ secrets.PROMOTE_APP_PRIVATE_KEY }}
          repositories: ${{ github.event.repository.name }}
          permission-contents: write   # the token can push commits, nothing else

      - name: Check out every branch
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Push the approved SHA to main as a fast-forward
        if: needs.preflight.outputs.fast_forward == 'true'
        env:
          SHA: ${{ needs.preflight.outputs.sha }}
          APP_TOKEN: ${{ steps.app.outputs.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          git remote set-url origin "https://x-access-token:${APP_TOKEN}@github.com/${REPO}.git"
          git fetch --quiet origin main
          if ! git merge-base --is-ancestor origin/main "$SHA"; then
            echo "::error::main moved and is no longer an ancestor of $SHA; start a new promotion"
            exit 1
          fi
          git push origin "$SHA:refs/heads/main"
          echo "::notice::main := $SHA"

      - name: Deploy prd and wait for the result
        env:
          SHA: ${{ needs.preflight.outputs.sha }}
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: bash scripts/deploy-env.sh main prd "$SHA"
```

### `scripts/deploy-env.sh`

Called by `deploy-dev`, `promote-stg` and `promote-prd`. It starts `infra.yml` on the target branch
(`workflow_dispatch` with `GITHUB_TOKEN` starts a run; a push with it would not), then waits for that run of the SHA,
so the deploy and its smoke test belong to the run that asked for them (CI-PROMOTE-01). A prd plan with changes parks
the run at `tf-apply-prd`: approve it within the 25-minute wait, or the promotion job fails while the `infra.yml` run
keeps waiting for the approval. App repos add their own deploy here.

```bash
#!/usr/bin/env bash
# deploy-env.sh <branch> <env> <sha> - start infra.yml on <branch> and wait for its result.
# Needs GH_TOKEN (actions: write) and REPO (owner/name).
set -euo pipefail

BRANCH="$1"
ENV_NAME="$2"
SHA="$3"
: "${GH_TOKEN:?}" "${REPO:?}"

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
gh workflow run infra.yml --repo "$REPO" --ref "$BRANCH" -f environment="$ENV_NAME" -f mode=apply

deadline=$((SECONDS + 1500))
while [ "$SECONDS" -lt "$deadline" ]; do
  run="$(gh run list --repo "$REPO" --workflow infra.yml --branch "$BRANCH" --event workflow_dispatch \
    --commit "$SHA" --created ">=$started" --limit 1 --json status,conclusion,url --jq '.[0] // empty')"
  if [ -n "$run" ]; then
    status="$(jq -r .status <<<"$run")"
    conclusion="$(jq -r .conclusion <<<"$run")"
    url="$(jq -r .url <<<"$run")"
    if [ "$status" = "completed" ]; then
      echo "infra.yml on $BRANCH ($ENV_NAME): $conclusion — $url" >> "${GITHUB_STEP_SUMMARY:-/dev/stdout}"
      [ "$conclusion" = "success" ] && exit 0
      echo "::error::the $ENV_NAME deploy ended '$conclusion': $url"
      exit 1
    fi
    # 'waiting' = parked at tf-apply-prd: approve the plan in that run.
    echo "infra.yml on $BRANCH is $status — $url"
  else
    echo "no infra.yml run for $SHA on $BRANCH yet"
  fi
  sleep 30
done
echo "::error::no completed infra.yml run for $SHA on $BRANCH within 25 minutes"
exit 1
```

### `.github/workflows/branch-sync.yml`

Runs on every push to `develop`/`stage`/`main` (and by hand), verifies the `main ⊆ stage ⊆ develop` ancestry
invariant, and opens a reconcile issue (lineage gap) or a back-merge PR (content) when `main` carries commits
`develop` lacks. No schedule (CI-COST-12): the weekly fleet-wide invariant check runs once, in the control repo
(GOV-PRV-04).

```yaml
name: branch-sync

on:
  push:
    branches: [develop, stage, main]
  workflow_dispatch:

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: branch-sync-${{ github.event.number || github.ref }}
  cancel-in-progress: true

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write
      pull-requests: write
      issues: write
    steps:
      - name: Check out every branch
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Inspect the branch chain
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

      - name: Open the lineage-gap issue
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

      - name: Open the back-merge PR
        if: steps.inspect.outputs.mode == 'pr'
        uses: actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0
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
            await github.rest.pulls.create({
              owner,
              repo,
              title: 'chore(sync): back-merge main into develop',
              head: branch,
              base: 'develop',
              body: 'Merge with a **merge commit**, never squash.',
            });
            core.info('Opened back-merge PR');
        env:
          MAIN_SHA: ${{ steps.inspect.outputs.main_sha }}

      - name: Fail on a broken chain
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

      - name: Fail on a sync gap
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

Required status check for PRs into `stage` and `main`: rejects every PR into `stage` and allows only `hotfix/*` heads
into `main`. `edited` re-runs the check when a PR changes its base branch.

```yaml
name: branch-policy

on:
  pull_request:
    branches: [stage, main]
    types: [opened, synchronize, reopened, edited]

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: branch-policy-${{ github.event.number || github.ref }}
  cancel-in-progress: true

jobs:
  branch-policy:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    steps:
      - name: Enforce the promotion policy
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

Read-only drift plan of `dev`/`stg`/`prd` against live state; opens or closes one `drift: <env>` issue per
environment. Started by hand (CI-COST-12 allows no schedule without an exception record); the plan legs bind
`<env>-plan` only, never a gated environment.

```yaml
name: tf-drift
run-name: tf-drift · ${{ github.sha }}

on:
  workflow_dispatch:

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: tf-drift-${{ github.ref }}
  cancel-in-progress: false

jobs:
  plan-dev:
    if: github.event_name == 'workflow_dispatch'
    permissions:          # a called workflow never gets more than its caller grants
      contents: read
      id-token: write
    uses: ./.github/workflows/_tf-plan.yml # zizmor: ignore[self-repository]
    with:
      environment: dev
      plan-environment: dev-plan
      cloud: azure
      tool: terraform
      working-directory: terraform
      lock: false
      ref: ${{ github.sha }}

  plan-stg:
    if: github.event_name == 'workflow_dispatch'
    permissions:
      contents: read
      id-token: write
    uses: ./.github/workflows/_tf-plan.yml # zizmor: ignore[self-repository]
    with:
      environment: stg
      plan-environment: stg-plan
      cloud: azure
      tool: terraform
      working-directory: terraform
      lock: false
      ref: ${{ github.sha }}

  plan-prd:
    if: github.event_name == 'workflow_dispatch'
    permissions:
      contents: read
      id-token: write
    uses: ./.github/workflows/_tf-plan.yml # zizmor: ignore[self-repository]
    with:
      environment: prd
      plan-environment: prd-plan
      cloud: azure
      tool: terraform
      working-directory: terraform
      lock: false
      ref: ${{ github.sha }}

  report:
    needs: [plan-dev, plan-stg, plan-prd]
    if: ${{ !cancelled() }}
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      issues: write
    steps:
      - name: Reconcile one drift issue per environment
        uses: actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0
        with:
          script: |
            const label = "tf-drift"
            const { data: issues } = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: "all",
              labels: label,
              per_page: 100,
            })
            for (const targetEnv of ["dev", "stg", "prd"]) {
              const exitcode = process.env[targetEnv.toUpperCase() + "_EXITCODE"]
              const title = "drift: " + targetEnv
              const existing = issues.find((i) => i.title === title && !i.pull_request)
              if (exitcode === "2") {
                const body =
                  "Terraform drift detected for environment `" + targetEnv + "`.\n\n" +
                  "The drift plan shows changes against the deployed state. " +
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
              } else if (exitcode === "0" && existing && existing.state === "open") {
                await github.rest.issues.update({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  issue_number: existing.number,
                  state: "closed",
                })
              } else if (exitcode !== "0") {
                core.warning("no plan result for " + targetEnv + "; the drift issue is unchanged")
              }
            }
        env:
          DEV_EXITCODE: ${{ needs.plan-dev.outputs.exitcode }}
          STG_EXITCODE: ${{ needs.plan-stg.outputs.exitcode }}
          PRD_EXITCODE: ${{ needs.plan-prd.outputs.exitcode }}
```

### `.github/actionlint.yaml`

actionlint config: lists self-hosted runner labels (none by default) so a new label is a reviewed change.

```yaml
# Add a label here before any workflow uses `runs-on: <self-hosted label>`.
self-hosted-runner:
  labels: []
```

### `.github/zizmor.yml`

zizmor config: the fleet reusable workflows (`VelimirMueller/*`) are pinned to a release tag (CI-STAGE-04); every
third-party action stays pinned to a full SHA.

```yaml
rules:
  unpinned-uses:
    config:
      policies:
        "VelimirMueller/*": ref-pin
```

### `.tflint.hcl`

tflint config at the repo root (TF-LAYOUT-06): keep the plugin of your cloud and delete the other block.

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

Weekly, grouped updates for GitHub Actions and Terraform into `develop`, at most five open PRs per ecosystem and a
7-day cooldown (CI-COST-04).

```yaml
version: 2

updates:
  - package-ecosystem: github-actions
    directory: /
    target-branch: develop
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    cooldown:
      default-days: 7
    groups:
      actions:
        patterns:
          - "*"

  - package-ecosystem: terraform
    directory: /terraform
    target-branch: develop
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    cooldown:
      default-days: 7
    groups:
      terraform:
        patterns:
          - "*"
```

## Terraform root

One root module in `terraform/` with the fixed file set (TF-FILE-01); per-environment values in
`envs/<env>.tfvars`, backend config in `envs/<env>.backend.hcl` (TF-LAYOUT-02). Generate the lock file once with
`terraform -chdir=terraform providers lock -platform=linux_amd64 -platform=linux_arm64 -platform=darwin_arm64` and
commit it as `terraform/.terraform.lock.hcl`. OpenTofu uses the same layout with `.opentofu-version`
([set-up-opentofu](../set-up-opentofu/SKILL.md)).

### `terraform/.terraform-version`

One exact version; `required_version` repeats it (TF-VER-01).

```text
1.13.4
```

### `terraform/versions.tf`

```hcl
terraform {
  required_version = "= 1.13.4"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.50"
    }
  }
}
```

### `terraform/backend.tf`

Backend block presenting both the azurerm and s3 state backend variants; the values come from
`envs/<env>.backend.hcl`.

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

### `terraform/providers.tf`

```hcl
provider "azurerm" {
  features {}
  use_oidc = true
}
```

### `terraform/variables.tf`

```hcl
variable "app" {
  type        = string
  description = "Short app name; the first part of every resource name."
}

variable "environment" {
  type        = string
  description = "Target environment."

  validation {
    condition     = contains(["dev", "stg", "prd"], var.environment)
    error_message = "environment must be dev, stg or prd."
  }
}

variable "location" {
  type        = string
  description = "Azure region of the resources."
  default     = "westeurope"
}
```

### `terraform/locals.tf`

```hcl
locals {
  name = "${var.app}-${var.environment}"

  tags = {
    project     = var.app
    environment = var.environment
    managed_by  = "terraform"
    repo        = "<owner>/<repo>"
  }
}
```

### `terraform/main.tf`

```hcl
resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name}"
  location = var.location

  tags = local.tags
}
```

### `terraform/outputs.tf`

```hcl
output "resource_group_name" {
  description = "Name of the main resource group."
  value       = azurerm_resource_group.main.name
}
```

### `terraform/envs/dev.tfvars`

Non-secret values only. `stg.tfvars` and `prd.tfvars` are the same with their environment name.

```hcl
app         = "<app>"
environment = "dev"
```

### `terraform/envs/dev.backend.hcl`

Per-environment backend config for `dev`, with the azurerm and s3 variants side by side. `stg.backend.hcl` and
`prd.backend.hcl` are the same with their environment name.

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

Idempotent bootstrap of the GitHub side of the pipeline (`public` variant): creates the nine environments
(`dev`/`stg`/`prd` deploy envs with deployment branch policies `develop`/`stage`/`main`, the `*-plan` plan envs, and the
`promote-stg`, `promote-prd`, `tf-apply-prd` gates with one user reviewer and self-review allowed), upserts one ruleset
per branch (`develop`, `stage`, `main`; the promotion App is the only bypass actor on `stage` and `main`), asserts
every gate has a reviewer and no admin bypass, and prints the repo's OIDC subject template.

```bash
#!/usr/bin/env bash
# setup-github.sh - idempotent GitHub bootstrap for the branch-promotion
# pipeline (public repos): the nine environments (deploy, plan, approval gates)
# with their deployment branch policies, and one ruleset per branch.
#
# Usage: setup-github.sh <owner/repo> <reviewer-login> <app-id>
#   <reviewer-login> is the GitHub user who approves the gates (the owner on a solo repo).
#   <app-id> is the numeric id of the promotion GitHub App (the bypass actor on stage and main).

set -euo pipefail

usage() {
  echo "usage: $0 <owner/repo> <reviewer-login> <app-id>" >&2
  exit 2
}

(($# == 3)) || usage

REPO="$1"
REVIEWER="$2"
APP_ID="$3"
# FLEET_CHECK=1 adds fleet-check to the required checks on develop; set it only once fleet-check.yml reports.
FLEET_CHECK="${FLEET_CHECK:-0}"

command -v gh >/dev/null 2>&1 || {
  echo "::error:: gh is required" >&2
  exit 1
}

[[ "${APP_ID}" =~ ^[0-9]+$ ]] || {
  echo "::error:: <app-id> must be the numeric id of the promotion App" >&2
  exit 2
}

# --------------------------------------------------------------- reviewer --

REVIEWER_ID="$(gh api "users/${REVIEWER}" --jq .id)"
[[ "${REVIEWER_ID}" =~ ^[0-9]+$ ]] || {
  echo "::error:: could not resolve user '${REVIEWER}'" >&2
  exit 1
}
echo "gate reviewer '${REVIEWER}': id ${REVIEWER_ID}"

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

# plan env: no reviewers, no branch policy (tf-drift.yml plans every env from one ref).
env_plan() {
  env_put "$1" <<'JSON'
{"deployment_branch_policy": null}
JSON
}

# gate env: one user reviewer; self-review allowed while the repo has one maintainer
# (prevent_self_review true would deadlock every gate, CI-GATE-03).
env_gate() {
  env_put "$1" <<JSON
{
  "reviewers": [{"type": "User", "id": ${REVIEWER_ID}}],
  "prevent_self_review": false,
  "can_admins_bypass": false
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
env_gate promote-stg
env_gate promote-prd
env_gate tf-apply-prd

# ---------------------------------------------------------------- rulesets --

# checks_json <context>... - required_status_checks entries.
checks_json() {
  local first=1 c
  for c in "$@"; do
    ((first)) || printf ','
    printf '{"context": "%s"}' "$c"
    first=0
  done
}

# ruleset_json <branch> - full ruleset body on stdout (GOV-RS-01..08, CI-CHECK-06).
ruleset_json() {
  local branch="$1" pr checks bypass strict
  case "${branch}" in
    develop)
      pr='"required_approving_review_count": 0, "dismiss_stale_reviews_on_push": true, "required_review_thread_resolution": true, "allowed_merge_methods": ["merge", "squash"]'
      if [[ "${FLEET_CHECK}" == 1 ]]; then checks="$(checks_json conclusion fleet-check)"; else checks="$(checks_json conclusion)"; fi
      strict=true
      bypass='[]'
      ;;
    stage | main)
      pr='"required_approving_review_count": 0, "dismiss_stale_reviews_on_push": true, "required_review_thread_resolution": true, "allowed_merge_methods": ["merge"]'
      if [[ "${branch}" == main ]]; then checks="$(checks_json conclusion branch-policy)"; else checks="$(checks_json branch-policy)"; fi
      strict=false
      bypass="[{\"actor_id\": ${APP_ID}, \"actor_type\": \"Integration\", \"bypass_mode\": \"always\"}]"
      ;;
    *)
      echo "::error:: no ruleset for branch '${branch}'" >&2
      return 1
      ;;
  esac
  cat <<JSON
{
  "name": "${branch}",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/heads/${branch}"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {${pr}}},
    {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": ${strict},
      "required_status_checks": [${checks}]}}
  ],
  "bypass_actors": ${bypass}
}
JSON
}

# upsert_ruleset <branch> - create or update, looked up by name (also the legacy "promotion: <branch>").
upsert_ruleset() {
  local branch="$1" id
  id="$(gh api "repos/${REPO}/rulesets" --paginate \
    --jq ".[] | select(.name == \"${branch}\" or .name == \"promotion: ${branch}\") | .id" | head -n 1 || true)"
  if [[ -n "${id}" ]]; then
    ruleset_json "${branch}" | gh api -X PUT "repos/${REPO}/rulesets/${id}" --input - >/dev/null
    echo "ruleset '${branch}' updated (id ${id})"
  else
    ruleset_json "${branch}" | gh api -X POST "repos/${REPO}/rulesets" --input - >/dev/null
    echo "ruleset '${branch}' created"
  fi
}

echo "== rulesets =="
upsert_ruleset develop
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
  bypass="$(gh api "repos/${REPO}/environments/${gate}" --jq '.can_admins_bypass')"
  if [[ "${bypass}" != "false" ]]; then
    echo "::error:: gate environment '${gate}' lets admins bypass it; untick 'Allow administrators to bypass' (GOV-ENV-06)" >&2
    exit 1
  fi
  echo "  ${gate}: required reviewers present, no admin bypass"
done

# -------------------------------------------------------------------- OIDC --

echo "OIDC subject template (for cloud OIDC federations):"
gh api "repos/${REPO}/actions/oidc/customization/sub" || echo "  (no custom template - default claims)"
```

## `private-free` variant

A private repo on GitHub Free has no environments, no reviewers and no rulesets (governance.md, "Variants"). The
dispatch is the approval (GOV-PRV-02). Changes against the files above:

- `infra.yml`: drop the `gate` job and the `environment:` line of `smoke`; in `_tf-plan.yml` and `_tf-apply.yml` drop
  `environment:` and read the identifiers from repo variables with the `_DEV`/`_STG`/`_PRD` suffix (SEC-04). A `prd`
  run uses `mode: plan`; the apply goes through `tf-apply-prd.yml` with that run id.
- `promote.yml`: drop `environment:` from `promote-stg`/`promote-prd`, add
  `github.triggering_actor == github.repository_owner` to their `if:`, and read `PROMOTE_APP_PRIVATE_KEY` as a repo
  secret.
- Skip `scripts/setup-github.sh`; GOV-PRV-05 replaces the rulesets with a local `pre-push` hook.

### `.github/workflows/tf-apply-prd.yml`

Applies one saved prd plan, by run id, from `main`, started by the owner. Copied from the governance example.

```yaml
name: tf-apply-prd

on:
  workflow_dispatch:
    inputs:
      plan_run_id:
        description: Run id of the prd plan to apply
        required: true

permissions: {}

defaults:
  run:
    shell: bash

concurrency:
  group: tf-apply-prd-prd
  cancel-in-progress: false

jobs:
  apply:
    if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && github.triggering_actor == github.repository_owner
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      id-token: write   # OIDC; trust subject <prefix>:ref:refs/heads/main
      actions: read
    steps:
      - name: Check out the main branch
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - name: Check that the plan run is a green infra.yml run on main
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
          RUN_ID: ${{ inputs.plan_run_id }}
        run: |
          set -euo pipefail
          read -r branch path conclusion < <(gh api "repos/$REPO/actions/runs/$RUN_ID" --jq '"\(.head_branch) \(.path) \(.conclusion)"')
          if [ "$branch" != "main" ] || [ "$path" != ".github/workflows/infra.yml" ] || [ "$conclusion" != "success" ]; then
            echo "::error::run $RUN_ID is $path on $branch ($conclusion); only a green infra.yml run on main holds a prd plan"
            exit 1
          fi
      - name: Download the saved prd plan
        uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          pattern: tfplan-prd-*
          merge-multiple: true
          path: terraform
          run-id: ${{ inputs.plan_run_id }}
          github-token: ${{ github.token }}
      - name: Read the pinned tool version
        id: version
        run: echo "version=$(tr -d '[:space:]' < terraform/.terraform-version)" >> "$GITHUB_OUTPUT"
      - name: Set up Terraform
        uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with:
          terraform_version: ${{ steps.version.outputs.version }}
          terraform_wrapper: false
      - name: Initialise the prd backend
        working-directory: terraform
        run: terraform init -input=false -lockfile=readonly -backend-config=envs/prd.backend.hcl
      - name: Apply the saved plan
        working-directory: terraform
        run: terraform apply -input=false tfplan
```

