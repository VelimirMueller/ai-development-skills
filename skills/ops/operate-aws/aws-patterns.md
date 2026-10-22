# AWS Patterns

Reference for [operate-aws](./SKILL.md). Commands follow the AWS CLI v2 docs as of 2026-10-22;
they were not run against a live account while writing this file. Run the read-only forms first.

## Rule: `get-caller-identity` before every session, `--profile` and `--region` on every command

**Why:** The CLI's implicit profile and region come from files and environment variables, and they
silently differ between machines and shells. A command run against the wrong account or region
either fails clearly or — much worse — succeeds against resources you did not mean to touch.
**How to apply:** `aws sts get-caller-identity --profile <profile> --region <region>` as the first
command of every session. Spell `--profile` and `--region` on every command, including ones you
"know" inherit correctly. Scripts fail fast if the vars are unset: `: "${AWS_PROFILE:?set --profile}"`.
**Anti-example:** `aws s3 ls` on a machine where `AWS_DEFAULT_REGION` points at a region the team
never uses — "the bucket vanished".

## Rule: "resource not found" usually means wrong region

**Why:** Most AWS services are regional. The console remembers its own region, the CLI remembers
another, and both disagree with the region the resource lives in. The result is a confident
wrong conclusion — deleted, never created, drift — when the resource is simply one region over.
**How to apply:** Before believing any "not found", check three regions: the CLI's
(`aws configure get region --profile <profile>`), the console's selector, and the resource's
expected region from the IaC config. `aws ec2 describe-instances` across your working set if
unsure.
**Anti-example:** Recreating an IAM-adjacent or regional resource "that Terraform lost", then
finding two of them in the next audit — one per region.

## Rule: no long-lived access keys — SSO profiles, and `export-credentials` into a subshell

**Why:** A long-lived key pair in `~/.aws/credentials` or a CI variable is a standing credential:
nothing expires it, every copy leaks it, and CloudTrail shows the leak as "you". SSO profiles
produce short-lived role credentials that expire by themselves.
**How to apply:** `aws configure sso` per account/role, `aws sso login --profile <profile>`. When
a tool insists on env vars, scope them: run the tool in a subshell with
`aws configure export-credentials --profile <profile> --format env` applied inside it, and never
write the values to a file or the interactive shell. Check `env | grep AWS_` after tooling runs.
**Anti-example:** `aws_access_key_id` committed "temporarily" for a local script, found by a
scanner two repos later.

## Rule: CI roles trust the OIDC subject *with the environment*, not the repo-wide subject

**Why:** A role that trusts `repo:<org>/<repo>:*` can be assumed by any workflow in the repo,
including a compromised PR build. Adding `:environment:<env>` means only a run that resolved that
GitHub environment — with its reviewers and branch policies — can mint the token.
**How to apply:** One role per environment; trust policy condition
`token.actions.githubusercontent.com:sub = repo:<org>/<repo>:environment:<env>` and
`aud = sts.amazonaws.com`. Wire: [set-up-terraform-pipeline](../../infra/set-up-terraform-pipeline/SKILL.md).
**Anti-example:** A single deployment role trusted repo-wide, used identically by a docs-only
workflow.

## Rule: Session Manager, not SSH

**Why:** SSH needs key material on instances, port 22 open to networks, and keys that outlive
people. Session Manager reaches the same instance through the SSM agent with IAM auth, full
CloudTrail logging, and no inbound ports.
**How to apply:** `brew install --cask session-manager-plugin`; `aws ssm start-session --target
<instance-id>`; port-forwarding with the `AWS-StartPortForwardingSession*` documents when a local
tool must reach a private service. Instance role needs the SSM managed-instance core policy.
**Anti-example:** A bastion host with a shared key "because the security group limits it to the
office IP" — an office IP that changed a year ago.

## Rule: bump `aws-cdk-lib` and the CDK CLI together

**Why:** The CLI reads the cloud assembly that `aws-cdk-lib` writes. They version in lockstep; a
mismatch fails with schema errors that name neither component — the error looks like a broken
app, and hours go to the wrong layer.
**How to apply:** One PR bumps both: the repo dependency (`aws-cdk-lib`) and the CLI
(`npm install -g aws-cdk@<matching>` — or the version pinned in the repo's toolchain file). CI
runs the CLI from the repo's toolchain, not a global install, so the lockstep is checked in.
**Anti-example:** Dependabot bumps `aws-cdk-lib` alone on a Friday; Monday's deploy fails with
"cloud assembly schema version 36 is not supported".

## Rule: Identity Center administration only from the management account or a delegated admin

**Why:** The permission set that administers Identity Center lives in the management account (or
a delegated administration account). The same `aws sso-admin` calls against a member account fail
or return partial views, which reads as "the permission sets are gone".
**How to apply:** Keep one profile bound to the management/delegated account for
`aws sso-admin`/`aws organizations` work; do that work there and nowhere else. Record which
account is the delegated admin in the runbook — it is the first thing forgotten in an incident.
**Anti-example:** "Recreating" permission sets in a member account after `list` returned empty.

## Rule: CloudTrail answers "who changed what" — query it before theorizing

**Why:** Every API change is in CloudTrail (within its delivery latency). Guessing the actor from
ticket history or memory produces confident, wrong blame; the lookup produces the username, time
and event name.
**How to apply:** `aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=<name>`
(switch the attribute key to `Username` or `EventName` as needed). For older or org-wide queries,
query the event data store in Athena — heavier, but complete.
**Anti-example:** A security-group change attributed to a deploy pipeline for two days; CloudTrail
names a human with a console session in five seconds.

## When to deviate

- **A tool with no SSO and no subshell isolation** (rare): a long-lived key scoped to one
  read-only IAM user, no inline policies beyond what the tool needs, rotation in the secrets
  inventory — [manage-secrets](../../infra/manage-secrets/SKILL.md).
- **LocalStack or a teaching sandbox:** keys and defaults are fine; the production rules apply
  the moment a real account ID is in the config.
- **Break-glass on prd:** a hand change during an incident is allowed — same record and revert
  rules as elsewhere; fold it back into IaC in the follow-up.
