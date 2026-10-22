# Stack Versions (ops)

Version floor for the ops skills — a floor, not a pin. "known locally 2026-10-22" means the tool
reported that line on this machine on that date; "API 2026-10-22" means it was read from the
tool's release source then. Every other row is **unverified — re-verify per
[version-protocol](../../core/_shared/version-protocol.md)** before it is pinned anywhere.

| Tool | Line | Verified from | Note |
|---|---|---|---|
| azure-cli | 2.90.0 | known locally 2026-10-22 (`az version`) | Extensions tracked per machine; list with `az extension list` |
| aws-cli | 2.37.6 | known locally 2026-10-22 (`aws --version`) | v2 line; SSO support is in v2 |
| `gh` | 2.102.0 | known locally 2026-10-22 (`gh --version`) | |
| `jq` | 1.8.2 | known locally 2026-10-22 (`jq --version`) | |
| `actionlint` | 1.7.12 | known locally 2026-10-22; GitHub releases | |
| `zizmor` | 1.30.1 | known locally 2026-10-22; GitHub releases | |
| Terraform | 1.17.0 | API 2026-10-22 | HashiCorp line |
| OpenTofu | 1.13.1 | API 2026-10-22 | Supported lines: 1.12.x until 2027-02-01, 1.13.x until 2027-08-01 ([infra table](../../infra/_shared/stack-versions.md)) |
| `tflint` | 0.64.0 | API 2026-10-22 | |
| `trivy` | 0.76.1 | API 2026-10-22 | CI runs the pinned container image `aquasec/trivy:0.76.1`, never the action |
| `pwsh` (PowerShell 7) | unverified — re-verify per version-protocol | — | `brew info --cask powershell` |
| `Microsoft.Graph` module | unverified — re-verify per version-protocol | — | `Find-Module Microsoft.Graph` in `pwsh` |
| `Microsoft.Graph.Entra` module | unverified — re-verify per version-protocol | — | `Find-Module Microsoft.Graph.Entra` |
| `ExchangeOnlineManagement` (v3) | unverified — re-verify per version-protocol | — | `Find-Module ExchangeOnlineManagement`; v3 line required |
| msgraph-cli (`mgc`) | unverified — re-verify per version-protocol | — | Status must be re-verified; treat as possibly archived |
| `azd` | unverified — re-verify per version-protocol | — | Only for azd projects |
| Bicep | unverified — re-verify per version-protocol | — | Only if the repo uses Bicep |
| AWS CDK CLI | unverified — re-verify per version-protocol | — | Must match the repo's `aws-cdk-lib` line |
| AWS SAM CLI | unverified — re-verify per version-protocol | — | |
| `session-manager-plugin` | unverified — re-verify per version-protocol | — | Cask `session-manager-plugin` |
| `granted` / `aws-vault` | unverified — re-verify per version-protocol | — | Optional profile helpers |
| `terraform-docs` | unverified — re-verify per version-protocol | — | |
| `infracost` | unverified — re-verify per version-protocol | — | |
| `conftest` | unverified — re-verify per version-protocol | — | |
| `pyairtable` | unverified — re-verify per version-protocol | — | Bundled CLI unverified |
| `httpie` | unverified — re-verify per version-protocol | — | |
| `yq` | unverified — re-verify per version-protocol | — | mikefarah's Go `yq` on brew |
| SigNoz | v0.145.0 | [infra table](../../infra/_shared/stack-versions.md), 2026-10-09 | Re-verify there |
| `otel-cli` | unverified — re-verify per version-protocol | — | Install path not confirmed |
| Airtable Web API | v0 | docs, stable for years | Rate limits: see [airtable-patterns](../operate-airtable/airtable-patterns.md) |

## Rule: re-verify, then record
**Why:** Every row above moves. A version pinned from memory or from this table without a live
check is a silent defect — the same rule as [version-protocol](../../core/_shared/version-protocol.md).
**How to apply:** Run the tool's own version command (or `Find-Module` in `pwsh`) and the registry
lookup before pinning. If a row disagrees with the live value, the live value wins; update this
file in the same change.
