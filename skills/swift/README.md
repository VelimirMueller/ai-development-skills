# Swift skills (vendored)

Third-party Swift and Apple-platform skills, picked from the community list
[twostraws/swift-agent-skills](https://github.com/twostraws/swift-agent-skills) on 2026-10-28.
Every skill here is MIT-licensed by its author; its `LICENSE` sits in the skill folder.

## What we changed

- Skill bodies and reference files are unchanged from the source commit below.
- **One exception, 2026-10-28:** `ios-simulator-skill/scripts/common/hang_sessions.py` gained a session-id check (`SessionStore._session_dir`): ids must match `hang-YYYYMMDD-HHMMSS-hex`, and the resolved path must stay inside the sessions dir. Without it, a crafted id could read a foreign `meta.json` and signal an arbitrary pid. Reported upstream.
- **Second exception, 2026-10-28:** `swift-security-expert/references/compliance-owasp-mapping.md` redacts Stripe's documentation example key (`sk_live_4eC39Hq…`) to `sk_live_REDACTED_EXAMPLE_FROM_STRIPE_DOCS` so GitHub push protection lets the vendored content into this public repo. The anti-pattern it illustrates is unchanged.
- Frontmatter only: `name` equals the folder name, and `description` starts with the skill's own "Use when …" clause, at most 300 characters, so `scripts/validate.sh` passes.
- Dropped: `.git*`, CI folders, test folders and duplicate plugin copies.
- Not taken: `figma-to-swiftui-skill` (no license), and the list's non-skill links.

## Not house style

- These skills follow their authors' conventions, not the audit-first format of the other catalogues.
- Some overlap on purpose (three concurrency skills, three testing skills, three SwiftData skills). Pick one per task.
- Before you update one, read the upstream diff: third-party skills run with your agent's permissions.

## Sources

| Skill | Author | Source | Commit |
|---|---|---|---|
| `app-intents` | Anton Novoselov | [n0an](https://github.com/n0an/App-Intents-Agent-Skill/tree/f754f08/app-intents) | `f754f08` |
| `app-store-aso` | Tim Broddin | [timbroddin](https://github.com/timbroddin/app-store-aso-skill) | `3f0b917` |
| `app-store-changelog` | Thomas Ricouard | [Dimillian](https://github.com/Dimillian/Skills/tree/05ba982/app-store-changelog) | `05ba982` |
| `appkit-accessibility-auditor` | Roberto Gómez Muñoz | [rgmez](https://github.com/rgmez/apple-accessibility-skills/tree/e469fe9/skills/appkit-accessibility-auditor) | `e469fe9` |
| `appstore-review` | Dann Beauregard | [3paws-ai](https://github.com/3paws-ai/mobile-ai-skills/tree/6d3570e/skills/appstore-review) | `6d3570e` |
| `asc-ad-hoc-distribution` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-ad-hoc-distribution) | `7de1ef7` |
| `asc-analytics-reports` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-analytics-reports) | `7de1ef7` |
| `asc-app-create-ui` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-app-create-ui) | `7de1ef7` |
| `asc-apple-ads` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-apple-ads) | `7de1ef7` |
| `asc-aso-audit` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-aso-audit) | `7de1ef7` |
| `asc-build-lifecycle` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-build-lifecycle) | `7de1ef7` |
| `asc-cli-usage` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-cli-usage) | `7de1ef7` |
| `asc-crash-triage` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-crash-triage) | `7de1ef7` |
| `asc-id-resolver` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-id-resolver) | `7de1ef7` |
| `asc-in-app-events` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-in-app-events) | `7de1ef7` |
| `asc-localize-metadata` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-localize-metadata) | `7de1ef7` |
| `asc-metadata-sync` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-metadata-sync) | `7de1ef7` |
| `asc-notarization` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-notarization) | `7de1ef7` |
| `asc-ppp-pricing` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-ppp-pricing) | `7de1ef7` |
| `asc-release-flow` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-release-flow) | `7de1ef7` |
| `asc-revenuecat-catalog-sync` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-revenuecat-catalog-sync) | `7de1ef7` |
| `asc-screenshot-resize` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-screenshot-resize) | `7de1ef7` |
| `asc-shots-pipeline` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-shots-pipeline) | `7de1ef7` |
| `asc-signing-setup` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-signing-setup) | `7de1ef7` |
| `asc-submission-health` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-submission-health) | `7de1ef7` |
| `asc-subscription-localization` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-subscription-localization) | `7de1ef7` |
| `asc-testflight-orchestration` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-testflight-orchestration) | `7de1ef7` |
| `asc-wall-submit` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-wall-submit) | `7de1ef7` |
| `asc-whats-new-writer` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-whats-new-writer) | `7de1ef7` |
| `asc-workflow` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-workflow) | `7de1ef7` |
| `asc-xcode-build` | Rudrank Riyam | [rudrankriyam](https://github.com/rudrankriyam/app-store-connect-cli-skills/tree/7de1ef7/skills/asc-xcode-build) | `7de1ef7` |
| `background-execution` | Anton Novoselov | [n0an](https://github.com/n0an/Background-Execution-Agent-Skill/tree/a29ddf8/background-execution) | `a29ddf8` |
| `core-data-expert` | Antoine van der Lee | [AvdLee](https://github.com/AvdLee/Core-Data-Agent-Skill/tree/855ca7d/core-data-expert) | `855ca7d` |
| `ios-accessibility` | Daniel Devesa | [dadederk](https://github.com/dadederk/iOS-Accessibility-Agent-Skill/tree/dcc3a36/ios-accessibility) | `dcc3a36` |
| `ios-code-audit` | Chad Etzel | [jazzychad](https://github.com/jazzychad/ios-code-audit) | `34edb29` |
| `ios-simulator-skill` | Conor Luddy | [conorluddy](https://github.com/conorluddy/ios-simulator-skill/tree/e38b3ad/ios-simulator-skill/skills/ios-simulator-skill) | `e38b3ad` |
| `observability` | Anton Novoselov | [n0an](https://github.com/n0an/Observability-Agent-Skill/tree/4ab4f37/observability) | `4ab4f37` |
| `swift-accessibility-skill` | Pasquale Vittoriosi | [PasqualeVittoriosi](https://github.com/PasqualeVittoriosi/swift-accessibility-skill/tree/3791850/swift-accessibility-skill) | `3791850` |
| `swift-api-design-guidelines-skill` | Erik Sebastián de Erice | [Erikote04](https://github.com/Erikote04/Swift-API-Design-Guidelines-Agent-Skill/tree/36cdc1b/swift-api-design-guidelines-skill) | `36cdc1b` |
| `swift-architecture-skill` | Lasha Efremidze | [efremidze](https://github.com/efremidze/swift-architecture-skill/tree/60e1776/swift-architecture-skill) | `60e1776` |
| `swift-concurrency` | Antoine van der Lee | [AvdLee](https://github.com/AvdLee/Swift-Concurrency-Agent-Skill/tree/d577081/skills/swift-concurrency) | `d577081` |
| `swift-concurrency-expert` | Thomas Ricouard | [Dimillian](https://github.com/Dimillian/Skills/tree/05ba982/swift-concurrency-expert) | `05ba982` |
| `swift-concurrency-pro` | Paul Hudson | [twostraws](https://github.com/twostraws/Swift-Concurrency-Agent-Skill/tree/bee3f69/swift-concurrency-pro) | `bee3f69` |
| `swift-focusengine-pro` | Michael Haviv | [mhaviv](https://github.com/mhaviv/Swift-FocusEngine-Agent-Skill) | `903d58d` |
| `swift-format-style` | Anton Novoselov | [n0an](https://github.com/n0an/Swift-FormatStyle-Agent-Skill/tree/5cda783/swift-format-style) | `5cda783` |
| `swift-security-expert` | Ivan Magda | [ivan-magda](https://github.com/ivan-magda/swift-security-skill/tree/bda2e0c/swift-security-expert) | `bda2e0c` |
| `swift-testing` | Eduardo Bocato | [bocato](https://github.com/bocato/swift-testing-agent-skill/tree/c2dd1b0/swift-testing) | `c2dd1b0` |
| `swift-testing-expert` | Antoine van der Lee | [AvdLee](https://github.com/AvdLee/Swift-Testing-Agent-Skill/tree/798e9b1/swift-testing-expert) | `798e9b1` |
| `swift-testing-pro` | Paul Hudson | [twostraws](https://github.com/twostraws/Swift-Testing-Agent-Skill/tree/2d6bba1/swift-testing-pro) | `2d6bba1` |
| `swiftdata-expert-skill` | Kudrin Dmitry | [vanab](https://github.com/vanab/swiftdata-agent-skill/tree/4819a53/swiftdata-expert-skill) | `4819a53` |
| `swiftdata-pro` | Paul Hudson | [twostraws](https://github.com/twostraws/SwiftData-Agent-Skill/tree/8051f17/swiftdata-pro) | `8051f17` |
| `swiftdata-testing` | Akshay Pimprikar | [akshaypimprikar](https://github.com/akshaypimprikar/ios-swiftdata-testing-agent-skill/tree/e8a9875/swiftdata-testing) | `e8a9875` |
| `swiftui-accessibility-auditor` | Roberto Gómez Muñoz | [rgmez](https://github.com/rgmez/apple-accessibility-skills/tree/e469fe9/skills/swiftui-accessibility-auditor) | `e469fe9` |
| `swiftui-design-principles` | Arjit Jaiswal | [arjitj2](https://github.com/arjitj2/swiftui-design-principles) | `791d22d` |
| `swiftui-performance-audit` | Thomas Ricouard | [Dimillian](https://github.com/Dimillian/Skills/tree/05ba982/swiftui-performance-audit) | `05ba982` |
| `swiftui-pro` | Paul Hudson | [twostraws](https://github.com/twostraws/SwiftUI-Agent-Skill/tree/f2920b6/swiftui-pro) | `f2920b6` |
| `swiftui-ui-patterns` | Thomas Ricouard | [Dimillian](https://github.com/Dimillian/Skills/tree/05ba982/swiftui-ui-patterns) | `05ba982` |
| `swiftui-view-refactor` | Thomas Ricouard | [Dimillian](https://github.com/Dimillian/Skills/tree/05ba982/swiftui-view-refactor) | `05ba982` |
| `uikit-accessibility-auditor` | Roberto Gómez Muñoz | [rgmez](https://github.com/rgmez/apple-accessibility-skills/tree/e469fe9/skills/uikit-accessibility-auditor) | `e469fe9` |
| `widgets` | Anton Novoselov | [n0an](https://github.com/n0an/Widgets-Agent-Skill/tree/06567e1/widgets) | `06567e1` |
| `writing-for-interfaces` | Andrew Gleave | [andrewgleave](https://github.com/andrewgleave/skills/tree/d6c72b8/writing-for-interfaces) | `d6c72b8` |
