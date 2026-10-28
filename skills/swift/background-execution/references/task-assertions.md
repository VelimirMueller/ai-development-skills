# Task assertions: finishing in-flight work

Use a task assertion to get extra time to **finish work that is already running** when the app moves to the background - flush a network request, finish a file write, close a database connection, save state. It is *not* for starting new long work or scheduling future work; for those use `BGTaskScheduler` (`bg-task-scheduler.md`) or a background `URLSession` (`background-url-session.md`).

Two APIs:

- `UIApplication.beginBackgroundTask` / `endBackgroundTask` - for apps (UIKit).
- `ProcessInfo.performExpiringActivity` - for app extensions (where `beginBackgroundTask` is unavailable), watchOS, and other non-UIKit contexts.

## beginBackgroundTask / endBackgroundTask

```swift
nonisolated func beginBackgroundTask(
    expirationHandler handler: (@MainActor @Sendable () -> Void)? = nil
) -> UIBackgroundTaskIdentifier                                     // iOS 4+

nonisolated func beginBackgroundTask(
    withName taskName: String?,
    expirationHandler handler: (@MainActor @Sendable () -> Void)? = nil
) -> UIBackgroundTaskIdentifier                                     // iOS 7+

nonisolated func endBackgroundTask(_ identifier: UIBackgroundTaskIdentifier)  // iOS 4+
```

`beginBackgroundTask` returns `UIBackgroundTaskIdentifier.invalid` when background running is not possible. Use `.invalid` as the "no live task" sentinel.

The load-bearing rules:

- **Every `beginBackgroundTask` must be balanced by exactly one `endBackgroundTask`.** If you do not end the task before time expires, the system **kills the app**.
- **You must call `endBackgroundTask` on both paths**: the normal completion path **and** inside the expiration handler. Make `end` idempotent so the two paths never double-end or leak.
- **Call `beginBackgroundTask` before starting the work**, ideally before the app actually backgrounds. The assertion is granted asynchronously; if you call it at the very end of `sceneDidEnterBackground(_:)`, the system may suspend you before it is granted, and your expiration handler fires immediately.
- The **expiration handler runs synchronously on the main thread**, briefly blocking suspension. Keep it minimal: stop work, call `end`, reset the id.
- **Multiple concurrent assertions are allowed**; each returns its own id and must be ended separately.
- `beginBackgroundTask`, `endBackgroundTask`, and `backgroundTimeRemaining` are safe to call off the main thread.
- `withName:` only sets a debugger-visible name; behavior is identical.
- **App extensions cannot call `beginBackgroundTask`** - use `performExpiringActivity`.

### Correctly bracketed example

```swift
import UIKit

final class DataUploader {
    private var backgroundTaskID: UIBackgroundTaskIdentifier = .invalid

    func sendDataToServer(_ data: Data) {
        // 1. Request the assertion EARLY, before starting the work.
        backgroundTaskID = UIApplication.shared.beginBackgroundTask(withName: "Finish upload") {
            [weak self] in
            // Expiration: runs on the main thread, shortly before time runs out.
            // MUST end the task or the app is killed.
            self?.endBackgroundTask()
        }

        // 2. Do the in-flight work off the main thread.
        DispatchQueue.global().async { [weak self] in
            guard let self else { return }
            self.upload(data)
            self.endBackgroundTask()           // 3. End on the success path too.
        }
    }

    private func endBackgroundTask() {
        guard backgroundTaskID != .invalid else { return }   // idempotent
        UIApplication.shared.endBackgroundTask(backgroundTaskID)
        backgroundTaskID = .invalid
    }

    private func upload(_ data: Data) { /* synchronous in-flight work */ }
}
```

### `backgroundTimeRemaining`

```swift
nonisolated var backgroundTimeRemaining: TimeInterval { get }   // iOS 4+
```

- Valid only after the app enters the background **and** has started at least one assertion while in the foreground.
- In the foreground (or before any assertion) it returns a huge placeholder (`.greatestFiniteMagnitude` / `DBL_MAX`) - **do not treat that as real budget**.
- **Do not rely on the exact value.** It is advisory; plan for ~**30 seconds** and always implement the expiration handler. The system may invoke the handler or terminate early under pressure.

## ProcessInfo.performExpiringActivity

```swift
func performExpiringActivity(withReason reason: String,
                             using block: @escaping @Sendable (Bool) -> Void)
// iOS 8.2+, tvOS 9+, watchOS 2+, Mac Catalyst 13.1+, visionOS 1+. NOT on macOS.
```

The assertion API for contexts where `UIApplication` is unavailable - **app extensions** (which may not call `beginBackgroundTask`), **watchOS**, and similar. The framework manages the assertion lifetime around the block; there is no manual begin/end id to balance. You only honor the `expired` flag:

- Block called with `expired == false` -> the assertion was granted; do the work.
- Block called (or **called again**) with `expired == true` -> the assertion could not be taken, or time ran out. **Stop in-progress work as fast as possible.**
- The block can run **twice** (once `false`, then `true` if the system needs to suspend), so it must be re-entrant and bail out promptly.

```swift
ProcessInfo.processInfo.performExpiringActivity(withReason: "Flush analytics queue") { expired in
    if expired {
        analytics.cancelInFlight()       // stop now
    } else {
        analytics.flushPendingEvents()   // do the work
    }
}
```

> On macOS there is no `performExpiringActivity`. Use `ProcessInfo.beginActivity` / `endActivity` to suppress App Nap for critical work - see `macos-background.md`.

## Assertions vs BGTaskScheduler

| | Task assertion | `BGTaskScheduler` |
|---|---|---|
| Intent | Finish work that is **already running** as the app leaves the foreground | Schedule **future** work |
| Wakes a suspended / terminated app? | No - it only extends the current run | Yes - the system launches/resumes the app to run the handler |
| Budget | Short, ~30 s | Longer windows; system-chosen time |
| API | `beginBackgroundTask` (apps), `performExpiringActivity` (extensions/watchOS) | `register` + `submit` |

Rule: "work is running and the user just backgrounded the app, let me finish it" -> assertion. "I want fresh data / deferred processing later" -> `BGTaskScheduler`. For a long network transfer specifically, do **not** try to hold the app alive on an assertion - hand it to a background `URLSession` so the system owns it past suspension (`background-url-session.md`).
