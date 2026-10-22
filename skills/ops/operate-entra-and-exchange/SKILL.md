---
name: operate-entra-and-exchange
description: Use when managing Entra ID or Exchange Online — app registrations vs enterprise apps, least-privilege Graph permissions, workload identity federation, credential expiry sweeps, shared mailboxes and scoped app access with az ad, az rest and the Graph and Exchange modules.
---

# Operate Entra ID and Exchange Online

Directory objects, not ARM resources — nothing here shows up in `az resource list`. Read-only by
default. **Never change prd by hand when the object is IaC-managed; change the code and promote it.**

## 1. Audit — signed in, and what exists (change nothing)

```bash
az login --tenant <tenant-id>
az ad signed-in-user show --query userPrincipalName -o tsv
az ad app list --display-name <app-name> --query '[].{appId:appId, objectId:id}' -o json    # app registrations
az ad sp list --display-name <app-name> --query '[].{id, appId}' -o json                    # enterprise apps (service principals)
az rest --method GET --url "https://graph.microsoft.com/v1.0/applications/<app-object-id>/federatedIdentityCredentials" --query 'value[].name' -o tsv
```

Credential expiry sweep (do this before anything else breaks):

```bash
az ad app credential list --id <app-id> --query '[].{key:displayName, end:endDateTime}' -o json            # client secrets
az ad app credential list --id <app-id> --cert --query '[].{key:displayName, end:endDateTime}' -o json     # certificates
```

Sign-in audit: `az rest --method GET --url 'https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=10&$filter=appId%20eq%20%27<app-id>%27'`
(single quotes, so the shell does not expand `$top`; the filter is URL-encoded). Exchange Online in `pwsh`: `Get-ConnectionInformation`
shows any open session.

## 2. Decide

- **Read-only investigation (default)** — lists, `show`, Graph GETs, sign-in logs.
- **The app or its permissions are IaC-managed** (`azuread` provider) — change the code, promote
  it ([set-up-terraform-pipeline](../../infra/set-up-terraform-pipeline/SKILL.md)).
- **One-off with a record** — consent grants, emergency secret rotation, group membership for an
  incident. Exact command and JSON output into the ticket; revert decision stated first.

## 3. Detect the track

| Signal | Track | Then |
|---|---|---|
| `grep -rn "azuread_" terraform/` covers the app | IaC | Read-only here; change via the pipeline |
| Apps created by hand or in the portal, history in tickets | Manual | One-off change with a record; move to IaC when touched a second time |
| Consent or role changes are scripted (`az rest` in the runbook) | Scripted | Extend the script, do not improvise beside it |

## 4. Install only what is missing

```bash
brew install --cask powershell          # pwsh — verify version before pinning (../_shared/stack-versions.md)
```

```powershell
Install-Module Microsoft.Graph -Scope CurrentUser
Install-Module Microsoft.Graph.Entra -Scope CurrentUser
Install-Module ExchangeOnlineManagement -Scope CurrentUser
```

`az ad` / `az rest` cover most work without any module — the full table is in
[cli-toolbox](../_shared/cli-toolbox.md). msgraph-cli (`mgc`) is *unverified — status must be
re-verified; treat as possibly archived*.

## 5. Do the work

**App registration vs enterprise app:** the *app registration* (object in your directory) defines
permissions; the *enterprise app* (service principal) is what consents, roles and assignments
attach to. `az ad app …` edits the first, `az ad sp …` and most Graph URLs address the second.
API permissions are what YOUR app requests (delegated = a signed-in user, application = app-only);
app roles are what YOUR api exposes to others.

**Admin consent (grant an application permission):**

```bash
az rest --method POST --url "https://graph.microsoft.com/v1.0/servicePrincipals/<sp-object-id>/appRoleAssignments" \
  --body '{"principalId":"<sp-object-id>","resourceId":"<resource-sp-object-id>","appRoleId":"<role-guid>"}'
```

**Least privilege:** `Sites.Selected` (per-site Graph access) instead of `Sites.ReadWrite.All`;
app-only `Mail.Send` scoped by Exchange **RBAC for Applications**, not tenant-wide. Every
application permission is a standing grant — prefer delegated, then the narrowest application set.

**Workload identity federation (preferred credential):**

```bash
az rest --method POST --url "https://graph.microsoft.com/v1.0/applications/<app-object-id>/federatedIdentityCredentials" \
  --body '{"name":"gha-prd","issuer":"https://token.actions.githubusercontent.com","subject":"repo:<org>/<repo>:environment:prd","audiences":["api://AzureADTokenExchange"]}'
```

Read the exact subject with `gh api repos/<org>/<repo>/actions/oidc/customization/sub` + `:environment:<env>`
(new tenants embed ids in the subject form). **Wait ~3 minutes** before the first use. Prefer
federated credentials over client secrets and certificates; a fresh or reset client secret can
401 for minutes — retry, do not re-reset.

**Graph call pattern:** page through `@odata.nextLink` until null; on 429 honour `Retry-After`
and never loop without a delay. Group-based access: `az ad group member add --group <group>
--member-id <object-id>`. Guest invitations via Graph can fail silently — check
`externalUserState` after inviting.

**Exchange Online (pwsh):**

```powershell
Connect-ExchangeOnline -UserPrincipalName <upn>                                  # interactive
Connect-ExchangeOnline -AppId <app-id> -CertificateThumbprint <thumbprint> -Organization "<tenant>.onmicrosoft.com>"

Get-Mailbox -ResultSize unlimited | Where-Object RecipientTypeDetails -eq 'SharedMailbox' | Select-Object PrimarySmtpAddress
Get-MessageTraceV2 -RecipientAddress <address>          # *unverified cmdlet name* — Get-MessageTrace on older lines
```

**RBAC for Applications** (replaces legacy application access policies), then wait — propagation
takes 30 minutes to 2 hours and can look inverted while running:

```powershell
New-ManagementScope -Name "<scope-name>" -RecipientRestrictionFilter "EmailLike('<pattern>')"
New-ManagementRoleAssignment -App <app-id> -Scope "<scope-name>" -Role "Application Mail.Send"
```

## 6. Wire

- **Client secrets** live in the secret store, never in the repo or a script:
  [manage-secrets](../../infra/manage-secrets/SKILL.md). Federated credentials need no secret at all.
- **Apps as code** — `azuread` provider resources in the IaC repo:
  [set-up-terraform-pipeline](../../infra/set-up-terraform-pipeline/SKILL.md).
- **CI access to Azure** is the federated credential above, one per environment.
- Tools and versions: [cli-toolbox](../_shared/cli-toolbox.md), [stack-versions](../_shared/stack-versions.md).

## 7. Verify

```bash
az ad app credential list --id <app-id> -o json | jq -r '.[].endDateTime'      # no surprise expiry
az rest --method GET --url "https://graph.microsoft.com/v1.0/applications/<app-object-id>/federatedIdentityCredentials" --query 'value[].subject' -o tsv
az ad sp show --id <app-id> --query 'appRoles[].value' -o json                 # permissions visible on the sp
```

```powershell
Get-ConnectionInformation | Format-Table State, UserPrincipalName, IsEopSession
```

An app-only Graph call made AS the app (token via the credential under test) is the only full
proof of a consent or federated credential — run it live in the environment that uses it.

## References
- [entra-exchange-patterns.md](./entra-exchange-patterns.md): the traps — object kinds, least
  privilege, federation, secret reset delays, paging and throttling, RBAC propagation, expiry sweeps.
- [cli-toolbox](../_shared/cli-toolbox.md), [stack-versions](../_shared/stack-versions.md).
- [operate-azure](../operate-azure/SKILL.md) for ARM resources; [manage-secrets](../../infra/manage-secrets/SKILL.md);
  [set-up-terraform-pipeline](../../infra/set-up-terraform-pipeline/SKILL.md).
- [security-baseline](../../core/_shared/security-baseline.md).
