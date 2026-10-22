# CLI Toolbox (ops)

One table per platform: the tool, how it installs, what it is for, how it signs in, and what to use instead of it.
Every install column carries the same rule: **verify version before pinning** — follow
[version-protocol](../../core/_shared/version-protocol.md) and record the line in
[stack-versions.md](./stack-versions.md). Versions for each tool: that file, not this one.

## Azure

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| `az` (Azure CLI) | `brew install azure-cli` | ARM resources, queries, RBAC, `az rest` | `az login --tenant <tenant-id>` then `az account set --subscription <subscription-id>` | Portal clicking for repeatable work |
| `az` extension `resource-graph` | `az extension add --name resource-graph` | `az graph query` across many subscriptions | inherits the `az` session | Per-subscription `az resource list` sweeps |
| `az` extension `account` | `az extension add --name account` | Subscription and tenant commands beyond core | inherits the `az` session | — |
| `azd` (Azure Developer CLI) | `brew install azd` | Only `azd` projects (`azd init`, `azd up`) | `azd auth login` | Do not install for plain CLI or Terraform repos |
| Bicep | `brew install bicep` (or `az bicep install`) | Only repos that already use Bicep | inherits the `az` session | — |
| Azure MCP server | configured in the MCP client, no brew | Resource lookup and changes from chat | per its config; `az login` still applies | Prefer it for exploration when present; CLI for scripts and audits |

## Entra ID (Microsoft Graph)

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| `az ad` / `az rest` | part of `azure-cli` | Apps, service principals, groups, raw Graph calls | `az login --tenant <tenant-id>` | Portal for anything repeatable or auditable |
| Microsoft Graph PowerShell SDK | `Install-Module Microsoft.Graph -Scope CurrentUser` in `pwsh` | Cmdlet coverage `az ad` lacks | `Connect-MgGraph -TenantId <tenant-id> -Scopes <scope>` | The `Az` module (ARM, not Graph) |
| `Microsoft.Graph.Entra` module | `Install-Module Microsoft.Graph.Entra -Scope CurrentUser` | Entra ID cmdlets (newer split of the SDK) | `Connect-Entra -TenantId <tenant-id>` | Older `AzureAD` module (deprecated) |
| `pwsh` (PowerShell 7) | `brew install --cask powershell` | Hosts the Graph and Exchange modules | n/a | Windows PowerShell 5.1 |
| msgraph-cli (`mgc`) | *unverified — status must be re-verified; treat as possibly archived* | Graph from a shell | n/a | Keep to `az rest` until verified |

## Exchange Online

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| `ExchangeOnlineManagement` v3 | `Install-Module ExchangeOnlineManagement -Scope CurrentUser` in `pwsh` | Mailboxes, mail flow, RBAC for Applications | `Connect-ExchangeOnline -UserPrincipalName <upn>` (interactive) or `-AppId <app-id> -CertificateThumbprint <thumbprint> -Organization <tenant-domain>` (app-only) | Basic-auth remote PowerShell (removed) |
| RBAC for Applications | via Exchange Online cmdlets | Scoping app-only `Mail.Send` and similar | via `Connect-ExchangeOnline` app-only | Application Access Policies (legacy path) |

## AWS

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| `aws` CLI v2 | `brew install awscli` | API operations, SSO profiles | `aws configure sso` once, then `aws sso login --profile <profile>` | Console clicking for repeatable work |
| `granted` (optional) | `brew install granted` | Many profiles, expiry prompts, console AssumeRole links | wraps SSO | Long-lived keys in `~/.aws/credentials` |
| `aws-vault` (optional) | `brew install aws-vault` | Credential isolation per profile, MFA | wraps SSO or IAM users | Long-lived keys in `~/.aws/credentials` |
| `session-manager-plugin` | `brew install --cask session-manager-plugin` | `aws ssm start-session` shell and port-forwarding | inherits the aws profile | SSH keys and open ports on instances |
| AWS CDK CLI | `npm install -g aws-cdk` | CDK apps — keep its version in lockstep with `aws-cdk-lib` | inherits the aws profile | — |
| AWS SAM CLI | `brew install aws-sam-cli` | Serverless local test and deploy | inherits the aws profile | — |
| AWS MCP server | configured in the MCP client | Resource lookup from chat | per its config | Prefer it when present; CLI for scripts |

## Airtable

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| Web API via `curl` / `httpie` | `brew install curl httpie` | Direct REST calls with a PAT | PAT in `AIRTABLE_API_KEY`, sent as `Authorization: Bearer <token>` | — |
| `pyairtable` | `pip install pyairtable` (includes a CLI — *unverified*) | Python scripts, typed table access, batching | PAT in the environment (`AIRTABLE_API_KEY`) | Raw curl loops in scripts |
| Airtable MCP | configured in the MCP client | Base exploration from chat | PAT in the MCP config | Prefer it when present; Web API for scripts |

## Terraform toolchain

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| `terraform` / `tofu` | `brew install terraform` / `brew install tofu` | State inspection (`state list`, `show`), plans | provider credentials per environment | — |
| `tflint` | `brew install tflint` | Lint before every plan | n/a | — |
| `trivy` | `brew install trivy` | Config and IaC scanning; CI runs the pinned container image, not an action | n/a | `aquasecurity/trivy-action` (compromised March 2026) |
| `terraform-docs` | `brew install terraform-docs` | Keep module docs in sync | n/a | Hand-written input tables |
| `infracost` | `brew install infracost` | Cost of a plan before apply | `infracost auth login` | — |
| `conftest` | `brew install conftest` | Policy checks on plans | n/a | — |

## GitHub

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| `gh` | `brew install gh` | PRs, checks, deployments API, the promotion workflow | `gh auth login` | Scraping the web UI |
| `actionlint` | `brew install actionlint` | Workflow lint | n/a | — |
| `zizmor` | `brew install zizmor` | Workflow security lint | n/a | — |

## Observability

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| SigNoz UI / API | browser or `curl` against `https://<signoz-host>` | Dashboards, alerts, log and trace search | per its auth setup | — |
| SigNoz MCP | configured in the MCP client | Alert and dashboard lookup from chat | per its config | Prefer it when present |
| `otel-cli` | *unverified — install path not confirmed* | Emitting test spans and metrics from a shell | n/a | — |

## General

| Tool | Install (verify version before pinning) | Use for | Sign-in | Use instead of |
|---|---|---|---|---|
| `jq` | `brew install jq` | Every JSON output below | n/a | Parsing JSON with grep |
| `yq` | `brew install yq` | YAML equivalents of jq | n/a | The Python `yq` (different syntax) |
