# Changelog

All notable changes to Swift FocusEngine Pro are documented here.

## [1.8.1] - 2026-08-30

### Verified
- **1.13x focus scale confirmed on tvOS 26** — measured in the tvOS 26.4 simulator: a SwiftUI `.card` button's 300×200pt content renders at 340×226 when focused (1.133x width / 1.130x height). The scale-matching table in `layout-patterns.md` now carries a simulator-measured evidence label instead of a "re-verify on tvOS 26" caveat; device re-measurement recommended only for pixel-critical work.

## [1.8.0] - 2026-08-30

### Added — OS 26 coverage, Swift 6.2 modernization, evidence labels

New-content release. Additions sourced from Apple documentation and release notes are labeled **doc-sourced** (not yet production-verified); no existing anti-pattern substance changed.

- **Evidence-label convention** (`anti-patterns.md` preamble): rules from the Apple API contract carry no label; rules from observed behavior carry a one-line `> Evidence:` label with platform/date. Labels added to #14 (Apple TV HD lag), #25–30 (production section), and the iOS game-controller section (Apple-documented: UIKit's Focus-based navigation collection lists game controllers as a focus input; exact button mappings remain device-verify).
- **Anti-pattern #28 strengthened**: documents that the `defaultFocus` API docs read as if `.userInitiated` covers user-driven navigation, while observed tvOS behavior is initial-appearance only — trust the observed behavior.
- **visionOS 26** (`visionos-focus.md`): opt-in gaze scrolling — `.scrollInputBehavior(.enabled, for: .look)` (`ScrollInputKind.look`, visionOS 26+); spatial accessories (PSVR2 Sense, Logitech Muse) as a pointer-class input alongside gaze.
- **RealityKit** (`realitykit-focus.md`): corrected nested style type names (`HoverEffectComponent.SpotlightHoverEffectStyle` etc.), real `ShaderHoverEffectInputs` shader signature and Shader Graph "Hover State" node outputs; new `HoverEffectComponent.GroupID` grouped-hover section; multi-platform availability note (iOS 18+/macOS 15+, pointer hover); visionOS 26 `ManipulationComponent`/`GestureComponent` overview.
- **tvOS 18+ TabView** (`layout-patterns.md`): `Tab` builder syntax (`.tabItem` soft-deprecated since 18), and `.sidebarAdaptable` focus-geometry implications (tab region moves to leading sidebar; #15/#16 escape direction changes).
- **tvOS 26 / Liquid Glass** (`focus-styling.md`): focused-control glass appearance, the Apple TV 4K (1st gen)/HD device-matrix caveat, `ControlSize` on tvOS 26+, the SDK-26 gesture-priority change, and a note to re-verify the 1.13x scale table on tvOS 26.
- **Swift 6.2 concurrency** (`async-focus.md`, `swiftui-focus.md`): UIKit async example rewritten around `Task {}` isolation inheritance (the `MainActor.run` wrapper was redundant from `@MainActor` contexts); new "Swift 6.2 isolation notes" (default MainActor isolation in new Xcode 26 projects, `nonisolated(nonsending)`, `@concurrent`); `AutoFocusManager` rewritten as `@MainActor @Observable` with `@ObservationIgnored` bookkeeping; background-thread guidance now prefers compiler-checked isolation over `DispatchQueue.main.async`.
- **`@FocusedObject` guard rails** (`ios-focus.md`, `macos-focus.md`): the API requires `ObservableObject`; `@Observable` models don't work with it — don't "modernize" that pattern.
- **macOS 26/27 notes** (`macos-focus.md`): Tahoe glass appearance note; macOS 27 beta items (menu-bar/status-item keyboard navigation, `autorecalculatesKeyViewLoop`, `NSTextSelectionManager`) plus the WWDC26 "Modernize your AppKit app" session reference.
- **New API: `accessibilityDefaultFocus(_:_:)`** (`accessibility-focus.md`) — the one focus API OS 26 added (all platforms 26.0+; default VoiceOver focus via `AccessibilityFocusState`). Found by scanning the installed 26.5 SDK swiftinterfaces across all five platforms — release-notes sweeps had missed it. That scan also upgrades the "no other new focus APIs, no deprecations in OS 26" claim from release-notes-supported to SDK-verified.
- **SKILL.md "Toolchain status" block**: OS 26 added exactly one focus API (above) and no deprecations; the 27 betas add none; the 27 SDKs require the scene-based lifecycle (iOS/iPadOS/tvOS/visionOS/Catalyst); tvOS 27 adds Dynamic Type.
- **Fixed (found in pre-release review):** the repo had referenced a nonexistent `recalculatesKeyViewLoop` NSWindow property since v1.3.0 — corrected to the real `autorecalculatesKeyViewLoop` in all six locations (SKILL.md, macos-focus.md, anti-patterns.md #19, debugging.md); the SDK-26 gesture-priority note now states the direction correctly (SwiftUI gestures now *yield* to existing UIKit/AppKit recognizers by default; `highPriorityGesture` to take precedence).

## [1.7.2] - 2026-08-30

### Fixed — correctness pass, verified against live Apple documentation

No anti-pattern substance changed. This release fixes API facts an agent would paste verbatim.

- **Nonexistent APIs removed.** `UIFocusDebugger.checkFocusGroupTree(for:)` → the real `focusGroups(for:)`, plus added `preferredFocusEnvironments(for:)` (debugging.md). `noteFocusRingChanged()` → the real `noteFocusRingMaskChanged()`, documented as a method you *call*, not an override point (focus-styling.md, macos-focus.md). `drawRect(_:)` → `draw(_:)` (focus-styling.md). Removed the non-functional `clipsToBoundsDisabled()` helper (its preference key had no definition or reader) in favor of real UIKit/SwiftUI clipping guidance.
- **`.focusSection()` is macOS 13+/tvOS 15+ only — removed the incorrect iOS 17+ claim** from ios-focus.md, macos-focus.md, and the accessibility Full Keyboard Access example, which is now built on `focusGroupIdentifier` (iOS 14+) as it must be on iOS.
- **`ScrollPosition` availability corrected to tvOS 18+/iOS 18+** (was 17+) in anti-patterns #26, async-focus.md, and layout-patterns.md, and all `ScrollPosition` examples now include the required `.scrollTargetLayout()`. The `ScrollViewReader` fallback guidance now correctly applies to all pre-18 deployment targets.
- **Availability annotations corrected:** `focusGroupIdentifier` iOS 14+ (was 15+), `UIFocusGuide` iOS 9+, `defaultFocus`/`.focusSection()` macOS 13+ (was 14+), `hoverEffect` iOS 13.4+/tvOS 16+ (table said tvOS 17+/N-A on iOS), `.defaultHoverEffect()` visionOS 1.0+ (was 2.0+), `UIFocusItemDeferralMode` iOS/tvOS 18+ (was 15+, semantics corrected to match docs), `prefersDefaultFocus` also available on macOS 12+.
- **SKILL.md output-format example no longer names the revoked `.allowsHitTesting(false)` rule** — it now states the action-gating rule with the anti-pattern #25 exception, matching the v1.5.0 correction.
- **visionOS fixes:** `HoverEffectGroup` example rewritten to real signatures (`hoverEffect(_:in:isEnabled:)` + `hoverEffectGroup()`); Dwell Control settings path corrected (Interaction, not AssistiveTouch); Switch Control no longer conflated with Dwell Control.
- **Full Keyboard Access description corrected** — it requires a hardware keyboard; what it extends is *reach* (all controls vs. text fields/lists).
- **Added `UIFocusSystem.requestFocusUpdate(to:)`** as the direct programmatic-focus API alongside the `preferredFocusEnvironments` pattern (uikit-focus.md), replacing the "ONLY correct way" overstatement.
- **Unverifiable WWDC citations removed** (macos-focus.md listed a WWDC21 session that doesn't exist and WWDC24 focus-ring content that couldn't be corroborated).
- **Structure/metadata sync:** anti-patterns.md sections reordered to document order (#18–24 before #25–30; numbers unchanged — note the macOS patterns were renumbered from #15–21 to #18–24 back in v1.4.0), SKILL.md references index updated to "30 numbered anti-patterns", plugin.json/marketplace.json counts and versions synced, package.json gained name+version, openai.yaml/llms.txt now include macOS, CONTRIBUTING gained the missing macos-focus.md row and current OS version numbers.

## [1.7.1] - 2026-06-04

### Fixed
- **Repo structure — `npx skills add` now resolves correctly.** The repo previously had both a root `SKILL.md` and a duplicate `swift-focusengine-pro/SKILL.md` subfolder (same skill name). Installers stopped at the root `SKILL.md` and copied the whole repo, leaving `references/` one level too deep and breaking the skill's own reference paths. The skill is now a single flat skill at the repo root (`SKILL.md` + `references/` + `agents/`); the duplicate subfolder is removed and `package.json` points at `.`. No skill-content changes from 1.7.0 — this is purely a packaging fix.
- Root `SKILL.md` description upgraded to the fuller write/review trigger text for better auto-activation.

## [1.7.0] - 2026-06-04

### Improved diagnosis (no new anti-patterns)

These edits make existing fixes findable from the symptom — the fix for section re-entry was already documented in anti-pattern #25, but nothing routed you to it from the observed behavior.

- **`swiftui-focus.md` — `focusSection()` "No last-focused memory" gotcha.** Explicit statement that, unlike UIKit's `remembersLastFocusedIndexPath`, `focusSection()` picks geometrically on every entry and remembers nothing. Names the common symptom (arrowing Up from a grid into a row of pills lands on the nearest pill, not the selected one) and routes to anti-pattern #25 for the fix. Notes that a reactive `onChange` redirect causes a visible hop and is not the fix.
- **`swiftui-focus.md` — section-width escape gotcha.** A `focusSection()` narrower than (or offset from) the content below it leaves columns with no section overhead, so Up escapes past it (e.g. to the tab bar). Fix: `.frame(maxWidth: .infinity, alignment: .leading)` before `.focusSection()`.
- **`focus-restoration.md` — ZStack `if/else` overlay restoration.** A hand-rolled overlay swap does not auto-restore focus like `.sheet()`/`.fullScreenCover()`. Documents the timing trap: a synchronous `@FocusState` assignment on dismiss is dropped because the target isn't rebuilt yet — defer with `Task { @MainActor in … }`.

## [1.6.0] - 2026-04-29

### Added
- **New tvOS anti-pattern #30** — Missing `preferredFocusEnvironments` override on UIKit view controllers with multiple focusable subviews. Without an explicit override, tvOS picks the geometrically first focusable view, which often lands on a secondary CTA (e.g., "Back to Home") instead of the primary action (e.g., "Sign In").
- **Absence-check trigger** — pr-review-style guidance now flags vertical `UIStackView` of buttons, focusable list + standalone buttons, conditional CTA, and modal/sheet presentations that lack a `preferredFocusEnvironments` override. Absence of the override is itself a finding.
- **`uikit-focus.md`: "When to override `preferredFocusEnvironments`" section** — enumerates the trigger conditions and provides a conditional-CTA pattern with `setNeedsFocusUpdate()` cross-reference (anti-pattern #7) for state changes after the view appears.
- Total anti-patterns: 30 (up from 29)

## [1.5.0] - 2026-04-13

### Added
- **5 new production tvOS anti-patterns** (#25–29) from large-scale media-app tvOS development:
  - #25: `.disabled()` on multiple list items with active selection state — mass-toggle focus cascade
  - #26: `ScrollViewReader.scrollTo()` inside `onChange` creates feedback loops with focus engine
  - #27: `@Observable` same-value mutation triggers unnecessary body re-evaluation
  - #28: `defaultFocus` with `.userInitiated` only fires on initial appearance, not re-entry
  - #29: Transient focus bouncing during navigation transitions (sidebar pass-through)
- **Production sidebar pattern** — dual `@FocusState` (container + per-item) with `.disabled()` gating for focus re-entry
- **UIKit reference-codebase sidebar comparison** — `remembersLastFocusedIndexPath`, container-level `isUserInteractionEnabled`, 0.5s debounce
- **`ScrollPosition` vs `ScrollViewReader`** — declarative scroll binding that doesn't fight the focus engine
- **Scroll edge fade patterns** — `.scrollEdgeEffectStyle(.soft)` (tvOS 26+), manual gradient mask with `.mask()`, `onGeometryChange` tracking
- **Focus scale matching** — reference 1.13x scale comparison table for SwiftUI `scaleEffect`
- **`@Observable` focus integration** — same-value guard, `@ObservationIgnored` for non-UI state
- **ScrollTo feedback loop documentation** — detailed cause/fix in `async-focus.md`
- **Focus cascade debugging guide** — structured logging patterns, what to look for in cascade logs
- **VoiceOver scroll animation guard** — check `UIAccessibility.isVoiceOverRunning` before animated scroll
- **Updated anti-pattern #1** — added caveat about `.allowsHitTesting(false)` reliability on tvOS
- **Updated SKILL.md core instructions** — `defaultFocus` re-entry limitation, `ScrollPosition` preference
- Total anti-patterns: 29 (up from 24)

## [1.4.0] - 2026-04-10

### Added
- **3 new tvOS anti-patterns from production** (#15–17) — `LazyVStack` focus escape, vertical `.focusSection()`, allocation in focus callbacks
- **VStack + inner LazyHStack pattern** — lightweight outer container stays in hierarchy, heavy content stays lazy inside each row
- **Tab bar focus escape detection** — `didUpdateFocus` pattern for detecting when focus escapes content to tab bar
- **VoiceOver card composition pattern** — `.accessibilityElement(children: .ignore)` with composed labels for multi-element focusable cards
- Total anti-patterns: 24 (up from 21)

## [1.3.0] - 2026-04-10

### Added
- **macOS focus coverage** — new `macos-focus.md` reference file (650+ lines)
  - AppKit: NSResponder chain, `acceptsFirstResponder`, `canBecomeKeyView`, key view loop
  - Key window vs main window, NSPanel focus behavior, `becomesKeyOnlyIfNeeded`
  - Focus ring: `NSFocusRingType`, `drawFocusRingMask()`, custom shapes
  - SwiftUI on macOS: `@FocusState`, `.focusable()`, `.focusSection()`, `.onKeyPress`
  - `focusedValue` / `focusedSceneValue` for menu bar commands
  - NSToolbar, NSPopover, sheets, NSAlert focus
  - Multi-window, multi-screen, external display
  - Mac Catalyst bridging
  - Full Keyboard Access
- **7 macOS-specific anti-patterns** (#15–21) in `anti-patterns.md`
- macOS focus ring styling in `focus-styling.md`
- macOS VoiceOver, NSAccessibility, Voice Control in `accessibility-focus.md`
- macOS first responder debugging in `debugging.md`
- macOS layout patterns (sidebar, toolbar, multi-window, inspector, three-column) in `layout-patterns.md`
- macOS focus restoration (sheets, NSDocument revert) in `focus-restoration.md`

## [1.2.0] - 2026-04-08

### Added
- **Expanded iOS focus coverage** — game controller focus, Stage Manager multi-window, `.onKeyPress`, pointer hover effects, `focusedValue` / `focusedSceneValue` deep dive
- **Expanded watchOS focus coverage** — `.digitalCrownAccessory()`, nested scrolling conflicts, managing multiple focusable controls
- FAQ section with 20 collapsible questions (tvOS, iOS, iPadOS, watchOS, visionOS, macOS)
- `llms.txt` for AI model discovery
- SKILL.md keyword metadata for registry indexing
- Community health files: CONTRIBUTING.md, issue templates, PR template

## [1.1.0] - 2026-04-07

### Added
- **watchOS focus reference** — Digital Crown routing, sequential focus, `.focusable()` ordering, Crown conflicts
- **RealityKit focus reference** — `HoverEffectComponent`, collision shapes, shader effects, mixed SwiftUI + RealityKit hierarchies
- **Accessibility focus reference** — `@AccessibilityFocusState`, VoiceOver coordination, Full Keyboard Access, Switch Control, Reduce Motion

## [1.0.0] - 2026-04-06

### Added
- Initial release with 10 reference files covering tvOS, iOS/iPadOS, and visionOS
- SwiftUI and UIKit focus management
- 14 critical anti-patterns
- Focus styling, restoration, layout patterns, async coordination, debugging
- Agent Skills format (SKILL.md) for Claude Code, Codex, Cursor, Copilot, Gemini CLI
