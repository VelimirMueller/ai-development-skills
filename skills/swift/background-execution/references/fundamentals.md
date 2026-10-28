# Fundamentals: the background execution model

Background execution on Apple platforms is **opportunistic, often discretionary, and tightly managed**. It is never guaranteed. The single most common class of bugs in this area comes from code that assumes background work runs promptly, runs to completion, or runs at all. It treats a privilege as a promise.

This file is the mental model. Read it first; the API-specific files build on it.

## Foreground, background, suspended

- **Foreground** - the app and everything it needs (frameworks, assets) are in memory and the app's interface is the focus on the device. Full CPU, full resources.
- **Background** - the user left the app but the process is still alive. **By default a backgrounded app is suspended.** A suspended app stays in memory but gets **no CPU time**. This protects battery life, preserves privacy, and frees resources for the foreground app.
- Background runtime is the system *temporarily* lifting that suspension so the app can do a discrete piece of work, then suspending it again.

Two distinct needs, served by two distinct families of API:

1. **Finish work that is already running** as the app leaves the foreground (a flush, a save, an in-flight upload). This is a *task assertion* - see `task-assertions.md`.
2. **Schedule future work** the system runs at a time of its choosing (refresh, maintenance, a download triggered by push). This is `BGTaskScheduler`, background `URLSession`, or background push - see the respective files.

Picking the wrong family is the root cause of most "my background code never runs" reports.

## The system's priorities (why your task may not run)

The system optimizes for the device owner, not for your app. Its goals: protect battery life, optimize performance, keep the foreground fluid and responsive. Every decision about whether to grant your app runtime flows from that.

The fundamental constraint is **energy**. Every operation - CPU cycles, GPU rendering, network requests, even Neural Engine inference - has a battery cost. Battery is finite, so the system **coalesces** background work: it wakes apps together when the device is already awake, rather than waking the device repeatedly. It also manages other shared resources - memory, CPU time, network bandwidth. A backgrounded app that uses too much memory or CPU is competing with the foreground app, and the system will **throttle, suspend, or terminate** it.

On iOS 26, Battery Settings shows per-app, background-specific battery impact. A power-hungry background app is visible to the user, who can then disable its background privileges.

The runtime environment is dynamic. The system weighs **network availability, CPU load, device activity, thermal state, and battery level** when deciding what to schedule. A perfectly written task may still be postponed because conditions are wrong right now. The queue of background work is never empty; the system may always choose to run something else first.

Cooperative apps are rewarded: the system observes which apps respond promptly to expiration, keep work small, and finish cleanly, and it uses that history to influence future scheduling. Greedy apps are scheduled less.

## The runtime budget, and why each mechanism runs at its own rate

Beyond the moment-to-moment conditions above, the system gives each app a slowly depleting **energy budget** and **cellular-data budget** over the course of a day; background work draws from both. Two practical consequences:

- **Keep each background refresh small.** Apple's guidance is to keep cellular data under roughly 100 KB per refresh - a good target for both `BGAppRefreshTask` and background pushes. Download only what is critical (thumbnails, not full images), prefer Wi-Fi, and enqueue the rest as a discretionary `URLSession` transfer.
- **Background App Refresh is usage-predicted.** The system uses on-device learning to run `BGAppRefreshTask` shortly before it expects the user to open the app, so refreshes are not evenly spaced through the day.

WWDC 2020 "Background Execution Demystified" names **seven factors** that gate background runtime: critically low battery, Low Power Mode, app usage, the App Switcher (force-quit), the Background App Refresh switch, system budgets (energy/data), and rate-limiting. Each mechanism is subject to a different subset, which is why they run at different rates and reliabilities:

- **Background App Refresh** is subject to **all seven**, so it is the least predictable.
- **Background processing tasks** are not gated by battery / Low Power Mode / energy budget (they run while charging and idle), but require the user to have opened the app within roughly the last two weeks; with daily charging, daily execution is achievable.
- **Background push** is *not* gated by app usage, but is throttled and delayed by rate-limiting (see `background-push.md`).
- **Background `URLSession`** is *not* gated by app usage. A **non-discretionary** transfer ("I need it now") is held back by almost nothing - essentially force-quit plus a greatly relaxed system budget - so it is the most dependable path; a **discretionary** transfer is deliberately deferred by the system to optimal conditions (Wi-Fi, charging), trading promptness for lower battery and data cost.

Levers that earn more runtime: **signal completion immediately** (call the completion handler / `setTaskCompleted`) so the system can suspend you into a low-power state, avoid waking unneeded hardware (GPS, accelerometer), serialize work so it finishes fast, and minimize cellular data.

## The user has the final say

Three user-facing toggles can suppress or curtail background work, and your code must degrade gracefully when they do:

- **Background App Refresh** (Settings, per-app and global). When off, `BGAppRefreshTask` and background fetch do not run. Check `UIApplication.shared.backgroundRefreshStatus` (`.available` / `.denied` / `.restricted`). On `.restricted` (parental controls / MDM) do **not** nag the user - they cannot change it.
- **Low Power Mode** (`ProcessInfo.processInfo.isLowPowerModeEnabled`). Reduces CPU/GPU, pauses discretionary and background activity, and **automatically disables Background App Refresh**. Back off your own discretionary work when it is on; observe `Notification.Name.NSProcessInfoPowerStateDidChange`.
- **Low Data Mode** - constrained networking. Honor it via `URLSessionConfiguration.allowsConstrainedNetworkAccess`.

See `testing-and-debugging.md` for reading these states and for thermal state (`ProcessInfo.thermalState`).

## Force-quit changes everything

If the **user force-quits the app** (swipes it up in the App Switcher), the system treats it as "I do not want this app running" and will **not relaunch it in the background** until the user manually launches it again. This single fact disables, all at once:

- `BGTaskScheduler` launches (`BGAppRefreshTask`, `BGProcessingTask`),
- silent / background push wake-ups (`content-available`),
- background `URLSession` completion relaunches.

A normal return to the Home screen (suspend) does **not** do this - only an explicit force-quit. Never design a feature whose correctness depends on background wake-ups for users who habitually force-quit.

## The five principles (WWDC 2025 "Get ahead with background tasks")

Apple frames good background citizenship as five properties. Use them as a review checklist:

- **Efficient** - if work does not need to run now, defer it (e.g. until charging). If it must run, keep it lightweight and purpose-driven.
- **Minimal** - keep background work small. Avoid bloated work; prefer batch processing to minimize memory footprint.
- **Resilient** - save incremental progress early and often; respond to expiration signals promptly and trust the system will return to your workload. Design work to pick up where it left off.
- **Courteous** - stay lightweight, honor user preferences, keep your impact proportional to the value delivered.
- **Adaptive** - keep work atomic, advertise your requirements (power/network) clearly, and adapt to system conditions.

## Four questions to ask before choosing an API

1. **Who initiated the task?** Explicit user action, or discretionary work that could run later?
2. **How long will it take?** Categorize: short (seconds), medium, long (minutes+).
3. **Is it critical to app state and freshness?** A background download adds liveliness; a telemetry upload has no immediate benefit to the device owner.
4. **Does it need user consent or input?** If yes, background runtime is the wrong tool - bring the work to the foreground instead.

Map the answers to an API with the decision tree in `SKILL.md`.

## The app / scene lifecycle

Modern apps are scene-based (iOS 13+). `UIScene.ActivationState`:

| State | Meaning |
|---|---|
| `.unattached` | Not connected to the app. |
| `.foregroundActive` | Foreground, receiving events. Full priority. |
| `.foregroundInactive` | Foreground but not receiving events (system alert, app switcher, incoming call). |
| `.background` | Running but not onscreen. No visible interface. |

There is no public `.suspended` activation state - suspension is a system runtime condition, not a delegate-visible scene state. You transition *into* suspension after the background grace period elapses.

Leaving the foreground: `foregroundActive -> foregroundInactive -> background -> (suspended)`. The system can disconnect a background or suspended scene at any time to reclaim resources, returning it to `.unattached`.

### What happens at the background transition

`sceneDidEnterBackground(_:)` (or the deprecated `applicationDidEnterBackground(_:)`) has roughly **5 seconds** to return. If it does not return in time, the app is terminated and purged. After it returns, the system suspends the app shortly after **unless you hold an active task assertion**. The system takes a snapshot for the App Switcher right after - so hide sensitive UI before backgrounding.

On the transition, do: save user data, close files, suspend dispatch/operation queues, invalidate timers, release the camera and other shared system resources, release recreatable in-memory objects, ensure Metal command buffers are scheduled, close shared-database connections. You do not need to discard asset-catalog images, `NSCache` contents, or `NSDiscardableContent`.

> `applicationDidEnterBackground(_:)` is deprecated. With scenes enabled, UIKit calls `sceneDidEnterBackground(_:)` instead. `UIApplication.didEnterBackgroundNotification` still posts either way.

### SwiftUI: `ScenePhase`

`@Environment(\.scenePhase)` exposes `.active` / `.inactive` / `.background`. Read from a `View` it reflects that scene; read from `App` it is an aggregate (`.active` if any scene is active). Use `.onChange(of: scenePhase)` to free resources when it becomes `.background` - "expect the app to terminate soon after." `ScenePhase` only *observes* the lifecycle; it does not grant background runtime. For that, use the APIs in the other reference files. See `swiftui-background-tasks.md`.

### The background execution sequence (launched into background)

When the system launches a not-running app to handle a background event (push, location, transfer completion, a scheduled task), the normal launch sequence runs, then `sceneDidEnterBackground(_:)` (or `applicationDidEnterBackground(_:)`) is called, then the triggering event is delivered, then a snapshot is taken, then the app may be suspended again. Crucially: **the app launches without its UI being constructed** - put background-relevant setup (`BGTaskScheduler` registration, session recreation, dependency wiring) where it runs on every launch path, not in `.onAppear` / view code that only runs when the UI appears.

## Which API for which job (one-line map)

| Need | API | File |
|---|---|---|
| Finish in-flight work while leaving foreground | `beginBackgroundTask` / `endBackgroundTask`; `performExpiringActivity` (extensions, watchOS) | `task-assertions.md` |
| Periodic content refresh before the user opens the app | `BGAppRefreshTask` | `bg-task-scheduler.md` |
| Long maintenance / ML / cleanup, ideally on charger | `BGProcessingTask` | `bg-task-scheduler.md` |
| User-initiated long work that continues after backgrounding, with system progress UI (iOS/iPadOS 26) | `BGContinuedProcessingTask` | `bg-task-scheduler.md` |
| Large/long file download or upload that survives suspension and termination | background `URLSession` | `background-url-session.md` |
| Server signals new content is available to fetch | background (silent) push | `background-push.md` |
| Incoming call invitation | PushKit + CallKit | `background-push.md` |
| Keep playing audio, or record the mic while locked | `audio` mode + active `AVAudioSession` | `background-audio.md` |
| Keep running for location / BLE / VoIP | a `UIBackgroundModes` capability | `background-modes.md` |
| Deferrable maintenance on macOS | `NSBackgroundActivityScheduler` | `macos-background.md` |

See `anti-patterns.md` for the mistakes these APIs invite.
