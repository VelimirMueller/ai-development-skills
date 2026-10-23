<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/banner/hero-v2-light.svg">
  <img alt="ai-development-skills. Opinions, packaged. Stable, v0.10.0. 93 skills in 9 plugins, one marketplace." src="assets/banner/hero-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/lead-v2-light.svg">
  <img alt="Senior engineering judgment as audit-first Claude Code skills. One plugin per domain: 93 skills across 9 plugins, shipped as the Claude Code marketplace ai-development-skills. It does not write your app. It tells you where the seams go." src="assets/readme/lead-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/stats-v2-light.svg">
  <img alt="93 skills across the set. 9 plugins, one per domain. 1 marketplace: ai-development-skills. 0 changes on a second run" src="assets/readme/stats-v2-dark.svg" width="100%">
</picture>
</p>

<br>

<p>
<img alt="01 WHAT IT DOES. Judgment, executable." src="assets/readme/divider-what-v2.svg" width="100%">
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/features-v2-light.svg">
  <img alt="Audit-first: Each skill reads what is already there and applies only the missing move. Run it twice: the second run is a no-op. Seams, not vendor calls: fetcher, captureError, env and queryKeys sit behind one point each. A vendor swap is a one-file change. Profile, not assumptions: The wizard writes .claude/stack-profile.md. Every skill reads it first, so defaults stay defaults" src="assets/readme/features-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/what-v2-light.svg">
  <img alt="One marketplace, MIT: Ships as the Claude Code marketplace ai-development-skills: 93 skills in 9 plugins, licensed MIT. Stacks it covers: React 19 / Vue 3 · Hono / Go / FastAPI · Supabase / Next 16 · Vercel / Hetzner / IONOS · Rust + Bevy. No change on a second run: Reads your stack profile first, applies only the missing move, and changes nothing on a second run. Judgment, not dogma: Every rule ships with its when to deviate. The aim is judgment, not dogma" src="assets/readme/what-v2-dark.svg" width="100%">
</picture>
</p>

<br>

<p>
<img alt="02 QUICK START. Two commands. One wizard." src="assets/readme/divider-start-v2.svg" width="100%">
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/start-v2-light.svg">
  <img alt="Terminal: $ /plugin marketplace add VelimirMueller/ai-development-skills | $ /plugin install devcore@ai-development-skills | # then ask Claude to &quot;set up my stack profile&quot;" src="assets/readme/start-v2-dark.svg" width="100%">
</picture>
</p>

<details>
<summary><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-16-v2-light.svg"><img alt="Plain text" src="assets/readme/links-16-v2-dark.svg" width="32%"></picture></summary>

```text
/plugin marketplace add VelimirMueller/ai-development-skills
/plugin install devcore@ai-development-skills
/plugin marketplace update ai-development-skills
```

</details>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/setup-v2-light.svg">
  <img alt="Run the wizard: Add the marketplace, install devcore, then ask Claude to &quot;set up my stack profile&quot;. The wizard detects the stack, asks only the gaps, writes .claude/stack-profile.md, and prints the plugins to enable. devcore comes along: Every plugin depends on devcore, so installing any of them installs it too. Small context cost: Each enabled skill keeps its one-line Use when description in context, and loads in full only when that line matches. Install what you use: Install only the plugins your stack uses; the rest cost nothing. One step per plugin: Claude Code 2.1.275 or later adds the marketplace on the way. See REFERENCE.md. Update: Run /plugin marketplace update ai-development-skills" src="assets/readme/setup-v2-dark.svg" width="100%">
</picture>
</p>

<br>

<p>
<img alt="03 HOW IT WORKS. Audit. Apply. Verify. No-op." src="assets/readme/divider-how-v2.svg" width="100%">
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/flow-v2-light.svg">
  <img alt="YOU ASK -&gt; CLAUDE MATCHES -&gt; AUDIT -&gt; APPLY -&gt; VERIFY. Run it twice and the second run is a no-op." src="assets/readme/flow-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/anatomy-v2-light.svg">
  <img alt="SKILL.md -&gt; stack-profile.md -&gt; YOUR REPO. devcore: every other plugin depends on it." src="assets/readme/anatomy-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/how-v2-light.svg">
  <img alt="Audit-first: Each skill inspects what is already there and applies only the missing move. A second run is a no-op. Seams carry across the chain: The router shares the queryClient with loaders, guards, forms and realtime. One OpenTelemetry pipeline ships every service&#x27;s telemetry to one collector. Profile, not assumptions: Every skill reads .claude/stack-profile.md first, so the author&#x27;s defaults (pnpm, Biome, tests in tests/) stay defaults. Full diagram: The full diagram and the composition chains are in REFERENCE.md" src="assets/readme/how-v2-dark.svg" width="100%">
</picture>
</p>

<br>

<p>
<img alt="04 USAGE. Ninety-three skills, condensed." src="assets/readme/divider-usage-v2.svg" width="100%">
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/plugins-v2-light.svg">
  <img alt="devcore@ai-development-skills: The stack-profile wizard, security and toolchain audits, commit and PR writing, release promotion. 7 skills. craftskills@ai-development-skills: Design patterns and OO principles, readable code, safe refactoring, clean tests, SOLID and the dependency rule, algorithms and data structures, debugging and estimation. 12 skills. frontendskills@ai-development-skills: Vite-SPA lifecycle (React 19 / Vue 3) plus landing &amp; content pages. 26 + 5 skills. backendskills@ai-development-skills: Hono / Go / FastAPI services, Supabase, Next 16. 15 skills. infraskills@ai-development-skills: Containers, OpenTofu, Terraform pipelines with approval gates, deploys, secrets, OTel collector. 10 skills. opsskills@ai-development-skills: Azure, Entra ID, Exchange Online, AWS, Airtable, alerting with SigNoz. 5 skills. cliskills@ai-development-skills: Command-line tools and the dev toolchain. 3 skills. aiskills@ai-development-skills: LLM seams, RAG, evals, MCP servers. 5 skills. gameskills@ai-development-skills: Rust + Bevy games. 5 skills" src="assets/readme/plugins-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/team-v2-light.svg">
  <img alt="Share with the team: Commit the same setup to the project&#x27;s .claude/settings.json, so everyone who trusts the folder gets the skills. The exact JSON is in REFERENCE.md. One profile per repo: Run the wizard once per repo and commit the resulting .claude/stack-profile.md. Validate: bash scripts/validate.sh checks every marketplace entry, the shared version, catalogue ownership, every SKILL.md, and every relative .md link under skills/. CI: CI runs the same script on every pull request" src="assets/readme/team-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/reading-v2-light.svg">
  <img alt="RATIONALE.md: The design narrative: every load-bearing decision as X over Y, for Z. CONTRIBUTING.md: The house style, and how to add a skill that fits. CHANGELOG.md: What landed, and when. REFERENCE.md: The full catalogue, install commands and run example. skills/core/_shared/stack-profile.md: The schema every skill reads first, and its precedence. skills/core/_shared/tech-radar.md: The Adopt/Hold lines the defaults come from. skills/core/_shared/security-baseline.md: The shared security bar behind audit-security and harden-backend. skills/core/_shared/audience.md: The audience contract: one text the junior can follow, the senior can verify, the CTO can skim. skills/frontend/_shared/architecture.md: The seam map: how one queryClient threads the whole app. skills/frontend/_shared/fetcher.md: The one canonical fetcher, base and auth versions. skills/backend/_shared/service-layout.md: One layering standard for TypeScript, Go, and Python. skills/landing/_shared/page-types.md: The public-page gate and the priority inversion" src="assets/readme/reading-v2-dark.svg" width="100%">
</picture>
</p>

<p align="center">
<a href="REFERENCE.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-1-v2-light.svg"><img alt="Reference (REFERENCE.md)" src="assets/readme/links-1-v2-dark.svg" width="32%"></picture></a>
<a href="RATIONALE.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-2-v2-light.svg"><img alt="Rationale (RATIONALE.md)" src="assets/readme/links-2-v2-dark.svg" width="32%"></picture></a>
<a href="CONTRIBUTING.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-3-v2-light.svg"><img alt="Contributing (CONTRIBUTING.md)" src="assets/readme/links-3-v2-dark.svg" width="32%"></picture></a>
</p>

<p align="center">
<a href="skills/core/_shared/stack-profile.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-4-v2-light.svg"><img alt="Stack profile (skills/core/_shared/stack-profile.md)" src="assets/readme/links-4-v2-dark.svg" width="32%"></picture></a>
<a href="skills/core/_shared/tech-radar.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-5-v2-light.svg"><img alt="Tech radar (skills/core/_shared/tech-radar.md)" src="assets/readme/links-5-v2-dark.svg" width="32%"></picture></a>
<a href="skills/core/_shared/security-baseline.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-6-v2-light.svg"><img alt="Security baseline (skills/core/_shared/security-baseline.md)" src="assets/readme/links-6-v2-dark.svg" width="32%"></picture></a>
</p>

<p align="center">
<a href="skills/core/_shared/audience.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-7-v2-light.svg"><img alt="Audience (skills/core/_shared/audience.md)" src="assets/readme/links-7-v2-dark.svg" width="32%"></picture></a>
<a href="skills/frontend/_shared/architecture.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-8-v2-light.svg"><img alt="Architecture (skills/frontend/_shared/architecture.md)" src="assets/readme/links-8-v2-dark.svg" width="32%"></picture></a>
<a href="skills/frontend/_shared/fetcher.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-9-v2-light.svg"><img alt="Fetcher (skills/frontend/_shared/fetcher.md)" src="assets/readme/links-9-v2-dark.svg" width="32%"></picture></a>
</p>

<p align="center">
<a href="skills/backend/_shared/service-layout.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-10-v2-light.svg"><img alt="Service layout (skills/backend/_shared/service-layout.md)" src="assets/readme/links-10-v2-dark.svg" width="32%"></picture></a>
<a href="skills/landing/_shared/page-types.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-11-v2-light.svg"><img alt="Page types (skills/landing/_shared/page-types.md)" src="assets/readme/links-11-v2-dark.svg" width="32%"></picture></a>
<a href="CHANGELOG.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-12-v2-light.svg"><img alt="Changelog (CHANGELOG.md)" src="assets/readme/links-12-v2-dark.svg" width="32%"></picture></a>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/ops-v2-light.svg">
  <img alt="One merge strategy: Every change enters at develop. stage and main get only fast-forwards, behind an approved promotion, so dev, stg and prd run the same commit. The contract: branch-promotion.md holds the rules. promote-release runs a promotion. set-up-terraform-pipeline wires the CI/CD that enforces it. Tool guides: Picture-first guides for Brevo, Airtable and Aircall: the parts, before and after, how it flows, the traps, and links to the official docs. Start here: Open guides/tools/README.md" src="assets/readme/ops-v2-dark.svg" width="100%">
</picture>
</p>

<p align="center">
<a href="skills/core/_shared/branch-promotion.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-17-v2-light.svg"><img alt="Branch promotion (skills/core/_shared/branch-promotion.md)" src="assets/readme/links-17-v2-dark.svg" width="32%"></picture></a>
<a href="skills/core/promote-release/SKILL.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-18-v2-light.svg"><img alt="Promote release (skills/core/promote-release/SKILL.md)" src="assets/readme/links-18-v2-dark.svg" width="32%"></picture></a>
<a href="skills/infra/set-up-terraform-pipeline/SKILL.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-19-v2-light.svg"><img alt="Terraform pipeline (skills/infra/set-up-terraform-pipeline/SKILL.md)" src="assets/readme/links-19-v2-dark.svg" width="32%"></picture></a>
</p>

<p align="center">
<a href="guides/tools/README.md"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-20-v2-light.svg"><img alt="Tool guides (guides/tools/README.md)" src="assets/readme/links-20-v2-dark.svg" width="32%"></picture></a>
</p>

<br>

<p>
<img alt="05 STATUS. One version, everywhere." src="assets/readme/divider-status-v2.svg" width="100%">
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/status-v2-light.svg">
  <img alt="Marketplace: ai-development-skills. Version: v0.10.0 · one version everywhere. Plugins: 9 · 93 skills. Validate: bash scripts/validate.sh. CI: validate on every pull request" src="assets/readme/status-v2-dark.svg" width="100%">
</picture>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/release-v2-light.svg">
  <img alt="v0.10.0: One marketplace, nine plugins, 93 skills. Built and run: Every code block in the catalogues was built and run in scratch projects on 2026-10-09. Anything not run is labelled unverified in place. Version floors: Versions are floors in each catalogue&#x27;s _shared/stack-versions.md. Validate: bash scripts/validate.sh exits 0 when every rule passes. Changes land in CHANGELOG.md" src="assets/readme/release-v2-dark.svg" width="100%">
</picture>
</p>

<details>
<summary><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-16-v2-light.svg"><img alt="Plain text" src="assets/readme/links-16-v2-dark.svg" width="32%"></picture></summary>

```bash
bash scripts/validate.sh   # exit 0: every rule passes
```

</details>

<p align="center">
<a href="https://www.claude.com"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-13-v2-light.svg"><img alt="Claude Code (https://www.claude.com)" src="assets/readme/links-13-v2-dark.svg" width="32%"></picture></a>
<a href="LICENSE"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-14-v2-light.svg"><img alt="MIT License (LICENSE)" src="assets/readme/links-14-v2-dark.svg" width="32%"></picture></a>
<a href="https://github.com/VelimirMueller"><picture><source media="(prefers-color-scheme: light)" srcset="assets/readme/links-15-v2-light.svg"><img alt="GitHub (https://github.com/VelimirMueller)" src="assets/readme/links-15-v2-dark.svg" width="32%"></picture></a>
</p>

<p>
<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/footer-v2-light.svg">
  <img alt="VM. studio / flagship · open source · look per vm-brand playbook · MIT (c) 2026 Velimir Mueller · -- EOF -- opinions, packaged --" src="assets/readme/footer-v2-dark.svg" width="100%">
</picture>
</p>
