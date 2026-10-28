# macOS background execution

macOS does not have `UIBackgroundModes`, `BGTaskScheduler` in the iOS sense (it arrives via Mac Catalyst), or `performExpiringActivity`. It has its own primitives:

- `NSBackgroundActivityScheduler` - deferrable, repeating maintenance (the macOS analogue of `BGTaskScheduler`).
- `ProcessInfo.beginActivity` / `endActivity` / `performActivity` - control App Nap and idle sleep for critical work.
- `SMAppService` - register persistent login items, agents, and daemons.

## NSBackgroundActivityScheduler

For low-priority, deferrable maintenance - backups, auto-save, periodic fetch, data cleanup, anything on intervals of roughly 10 minutes or more. Like a `Timer`, but the **system chooses the most efficient time** based on energy, thermal, and CPU conditions. macOS 10.10+.

```swift
import Foundation

final class MaintenanceScheduler {
    private let sut = NSBackgroundActivityScheduler(identifier: "com.example.MyApp.maintenance")

    func start() {
        sut.repeats = true
        sut.interval = 60 * 60          // average ~1 hour (repeating)
        sut.tolerance = 15 * 60         // fire window (default = interval / 2)
        sut.qualityOfService = .background

        sut.schedule { [weak self] completion in
            guard let self else { completion(.finished); return }

            let info = ProcessInfo.processInfo
            if info.isLowPowerModeEnabled
                || info.thermalState == .serious || info.thermalState == .critical {
                completion(.deferred)        // try again at a better time
                return
            }

            // ... do a chunk of work; check shouldDefer on long runs ...
            completion(self.sut.shouldDefer ? .deferred : .finished)
        }
    }

    func stop() { sut.invalidate() }    // in-flight block still finishes
}
```

- The block runs on a serial background queue; the system wraps it in `beginActivity` automatically based on QoS.
- **You must call the completion handler** with `.finished` or `.deferred`, or the activity is **never rescheduled**. On `.deferred` you may adjust `interval`/`tolerance` first.
- Poll `shouldDefer` during long runs (e.g. the user unplugged AC) and bail out.
- The `identifier` should be a constant reverse-DNS string; the system uses it to track run history and refine future scheduling. Changing it resets that history.

## ProcessInfo.beginActivity - suppress App Nap

App Nap throttles a hidden, idle app (suspends timers, slows the run loop, lowers I/O priority) to save energy. Wrap genuinely important non-UI work so the system does not nap the app for its duration. iOS 7+, macOS 10.9+ (most relevant on macOS).

```swift
let info = ProcessInfo.processInfo

// Manual - keep begin/end balanced or you pin the machine awake.
let token = info.beginActivity(options: [.userInitiated, .idleSystemSleepDisabled],
                               reason: "Exporting project")
defer { info.endActivity(token) }
performExport()

// Scoped - preferred, no token to leak:
info.performActivity(options: .userInitiated, reason: "Indexing library") {
    rebuildIndex()
}
```

`ProcessInfo.ActivityOptions`: `.idleDisplaySleepDisabled`, `.idleSystemSleepDisabled`, `.suddenTerminationDisabled`, `.automaticTerminationDisabled`, `.userInitiated` (suppresses App Nap), `.userInteractive`, `.userInitiatedAllowingIdleSystemSleep`, `.background`, `.latencyCritical`. Always balance `beginActivity` with `endActivity` (or use `performActivity`); a leaked token keeps the Mac awake / out of App Nap indefinitely.

## SMAppService - persistent background helpers

For a **persistent** background service (vs deferrable maintenance), use Service Management. `SMAppService` (macOS 13+, Mac Catalyst 16+) registers login items, LaunchAgents, and LaunchDaemons bundled in the app - replacing the deprecated `SMLoginItemSetEnabled` / `SMJobBless` / manual plist installs.

```swift
import ServiceManagement

let service = SMAppService.agent(plistName: "com.example.MyApp.helper.plist")
do { try service.register() } catch { print("register failed: \(error)") }
// service.status: .notRegistered / .enabled / .requiresApproval / .notFound
// SMAppService.openSystemSettingsLoginItems()  // deep link to the settings pane
```

Factory variants: `SMAppService.mainApp`, `.agent(plistName:)`, `.daemon(plistName:)`, `.loginItem(identifier:)`.

macOS UX rules worth encoding:

- Registering notifies the user, who can disable the service in System Settings -> General -> Login Items and Extensions. **Test the disabled state** and branch on `status`.
- If the app keeps running after the user quits, macOS shows a Dock indicator and a "Stop running in background" menu item; repeated stops can permanently block future background activity. Keep background work **visible** (Dock, menu bar / `MenuBarExtra`, progress UI).
- Non-UI / agent processes should opt into sudden/automatic termination via `Info.plist` (`NSSupportsSuddenTermination`, `NSSupportsAutomaticTermination`) and quit a few seconds after finishing.

## Cross-platform map

| API | iOS | macOS | watchOS | tvOS |
|---|---|---|---|---|
| `BGTaskScheduler` | 13+ | Catalyst 13.1+ | 26+ | 13+ |
| `NSBackgroundActivityScheduler` | - | 10.10+ | - | - |
| `beginActivity` / `endActivity` / `performActivity` | 7+ | 10.9+ | 2+ | 9+ |
| `performExpiringActivity` | 8.2+ | no | 2+ | 9+ |
| `SMAppService` | Catalyst 16+ | 13+ | - | - |

Rule of thumb: iOS family uses `BGTaskScheduler` (+ `performExpiringActivity` for short bursts). macOS uses `NSBackgroundActivityScheduler` (deferrable maintenance) + `beginActivity` (App Nap control) + `SMAppService` (persistent helpers). `beginActivity` is the only one of these on every platform.
