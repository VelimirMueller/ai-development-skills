# BGTaskScheduler and the BackgroundTasks framework

`import BackgroundTasks`. This framework schedules code to run when the app is backgrounded or suspended, and (iOS/iPadOS 26) continues foreground-initiated work into the background with system progress UI. iOS/iPadOS 13+, tvOS 13+, visionOS 1+, Mac Catalyst 13.1+, watchOS 26+ (earlier watchOS used WatchKit's `WKRefreshBackgroundTask`).

## The task types

All task classes inherit `BGTask` (`identifier: String`, `expirationHandler: (() -> Void)?`, `func setTaskCompleted(success: Bool)`). All request classes inherit `BGTaskRequest` (`identifier: String`, `earliestBeginDate: Date?`).

| Task | Request | Purpose | Time budget | When it runs | Extra request options |
|---|---|---|---|---|---|
| `BGAppRefreshTask` | `BGAppRefreshTaskRequest` | Short content refresh (feed, quotes) before the user opens the app | ~30 s | Opportunistically, aligned to the user's app-usage history; frequently-used apps are scheduled more | `earliestBeginDate` only |
| `BGProcessingTask` | `BGProcessingTaskRequest` | Long maintenance, ML, DB cleanup, large transfers | Minutes, interruptible | When the device is idle (typically charging + idle). The system **terminates a running processing task when the user picks up the device** (refresh tasks are exempt) | `requiresExternalPower`, `requiresNetworkConnectivity`, `earliestBeginDate` |
| `BGContinuedProcessingTask` (iOS/iPadOS 26+) | `BGContinuedProcessingTaskRequest` | **User-initiated** long work that starts in foreground and continues after backgrounding, with a system Live Activity showing progress | Runs until done, expired, or user-cancelled | **Immediately** on submission (or queued); must follow an explicit user action | `title`, `subtitle`, `requiredResources`, `strategy` |
| `BGHealthResearchTask` (iOS 17+) | `BGHealthResearchTaskRequest` | Long processing for health-research study data | Same as processing (it is a `BGProcessingTask` subclass) | Same as processing | All processing options + `protectionTypeOfRequiredData` |

`earliestBeginDate` is a **floor, not a schedule**: "the system doesn't guarantee launching the task at the specified date, but only that it won't begin sooner." `nil` means no delay.

## Registration (exact, and where)

```swift
@discardableResult
func register(forTaskWithIdentifier identifier: String,
              using queue: dispatch_queue_t?,
              launchHandler: @escaping (BGTask) -> Void) -> Bool
```

Rules:

- Call on `BGTaskScheduler.shared`. `queue: nil` uses a default background queue.
- **All launch handlers must be registered before launch finishes** - in `App.init()` (SwiftUI) or `application(_:didFinishLaunchingWithOptions:)` (UIKit). The system may launch the app directly into the background to run a task, and the handler must already be registered.
- **One handler per identifier.** Registering the **same identifier twice crashes the app.** Returns `false` if the identifier is not listed in `BGTaskSchedulerPermittedIdentifiers`.
- An app extension can *submit* a request, but the *main app* must *register* the handler; the system launches the app to run it.
- **iOS 26 exception:** `BGContinuedProcessingTask` handlers do **not** need to register before launch finishes - register dynamically when the user expresses intent (see below).

## Info.plist and capabilities (exact keys)

- `BGTaskSchedulerPermittedIdentifiers` - array of `String`. Every identifier you register or submit must appear here, or `register` returns `false` and `submit` throws `.notPermitted`. Xcode label: "Permitted background task scheduler identifiers".
- `UIBackgroundModes` - add `fetch` (Xcode: "Background fetch") for `BGAppRefreshTask`; add `processing` (Xcode: "Background processing") for `BGProcessingTask`. Set via Signing and Capabilities -> Background Modes.
- Identifiers are reverse-DNS, prefixed with the bundle ID: `com.example.myapp.refresh`, `com.example.myapp.db_cleaning`.
- `BGContinuedProcessingTask` GPU use needs the **Background GPU Access** capability (entitlement `com.apple.developer.background-tasks.continued-processing.gpu`).

> Adding `BGTaskSchedulerPermittedIdentifiers` disables the legacy `application(_:performFetchWithCompletionHandler:)` / `setMinimumBackgroundFetchInterval(_:)` path. Use `BGAppRefreshTask` instead - see `background-modes.md`.

## Submitting a request

```swift
// Preferred (captures all error conditions; do NOT call on the main thread):
func submitTaskRequest(_ taskRequest: BGTaskRequest) async throws
func submitTaskRequest(_ taskRequest: BGTaskRequest, completionHandler: @escaping @Sendable ((any Error)?) -> Void)

// Widely used, still valid since iOS 13, now deprecated in favor of the above:
func submit(_ taskRequest: BGTaskRequest) throws
```

- **Resubmitting an identifier that is already queued replaces** the previous request.
- **Limits:** at most **1 refresh task and 10 processing tasks** pending at once. Exceeding throws `.tooManyPendingTaskRequests`.
- Requests are **one-shot**. To make a task recur, **reschedule the next request at the start of the launch handler** (first line), before doing the work.
- Inspect / cancel: `getPendingTaskRequests(completionHandler:)`, `cancel(taskRequestWithIdentifier:)`, `cancelAllTaskRequests()`.

## Expiration and completion (do this exactly)

- Set `task.expirationHandler` to a closure that **quickly flips a flag / cancels work**. It fires shortly before time runs out and may fire before the full budget. Keep it tiny.
- Call `task.setTaskCompleted(success:)` **exactly once** when work finishes (or in the expiration handler with `success: false`).
- If you set **no** expiration handler, the system silently marks the task **complete and unsuccessful** rather than warning you - always set one.
- Calling `setTaskCompleted` **zero times** (running past expiration without it) can make the system **kill the app** and penalize future scheduling.

## BGAppRefreshTask - complete example

```swift
import BackgroundTasks

let refreshID = "com.example.myapp.refresh" // also in BGTaskSchedulerPermittedIdentifiers

// In App.init() / didFinishLaunching:
BGTaskScheduler.shared.register(forTaskWithIdentifier: refreshID, using: nil) { task in
    handleAppRefresh(task: task as! BGAppRefreshTask)
}

func scheduleAppRefresh() {
    let request = BGAppRefreshTaskRequest(identifier: refreshID)
    request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60) // no sooner than 15 min
    do { try BGTaskScheduler.shared.submit(request) }
    catch { print("Could not schedule app refresh: \(error)") }
}

func handleAppRefresh(task: BGAppRefreshTask) {
    scheduleAppRefresh()                 // reschedule the NEXT occurrence first

    let operation = RefreshContentsOperation()
    task.expirationHandler = { operation.cancel() }
    operation.completionBlock = {
        task.setTaskCompleted(success: !operation.isCancelled)
    }
    operationQueue.addOperation(operation)
}
```

Call `scheduleAppRefresh()` once when the app backgrounds, too, so the first cycle is primed.

## BGProcessingTask - complete example

```swift
let cleaningID = "com.example.myapp.db_cleaning"

BGTaskScheduler.shared.register(forTaskWithIdentifier: cleaningID, using: nil) { task in
    handleProcessing(task: task as! BGProcessingTask)
}

func scheduleProcessing() {
    let request = BGProcessingTaskRequest(identifier: cleaningID)
    request.requiresExternalPower = true        // run only on charger
    request.requiresNetworkConnectivity = false
    request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60)
    do { try BGTaskScheduler.shared.submit(request) } catch { print(error) }
}

func handleProcessing(task: BGProcessingTask) {
    scheduleProcessing()
    let operation = DatabaseMaintenanceOperation()
    task.expirationHandler = { operation.cancel() }
    operation.completionBlock = { task.setTaskCompleted(success: !operation.isCancelled) }
    operationQueue.addOperation(operation)
}
```

`requiresExternalPower` / `requiresNetworkConnectivity` exist **only** on `BGProcessingTaskRequest` (and its health-research subclass), not on app-refresh.

## BGContinuedProcessingTask (iOS / iPadOS 26)

For **user-initiated** long work - export a file, publish a post, finish an accessory update - that begins in the foreground and must complete reliably even if the user leaves. The system shows a Live Activity with your title/subtitle and the task's progress; the user can cancel it.

How it differs from the others: it starts from an **explicit user action**, begins **immediately** (not deferred), is **user-visible**, and **must report progress** - a task that reports no progress is expired and its resources reclaimed. **Do not** use it for automatic work (maintenance, backups, photo sync); the system cancels tasks that start without explicit user action.

API surface:

```swift
class BGContinuedProcessingTask: BGTask, ProgressReporting {
    var title: String
    var subtitle: String
    func updateTitle(_ title: String, subtitle: String)
    var progress: Progress           // from ProgressReporting; you MUST drive this
}

class BGContinuedProcessingTaskRequest: BGTaskRequest {
    init(identifier: String, title: String, subtitle: String)
    var requiredResources: Resources         // OptionSet; member: .gpu
    var strategy: SubmissionStrategy         // .queue (default) or .fail
}

// On the scheduler:
class var supportedResources: BGContinuedProcessingTaskRequest.Resources { get }  // check before requesting
```

Identifiers support a **wildcard** form: `<bundle-id>.<context>.*`, where a dynamic suffix is appended at registration and submission - useful when you submit many distinct instances.

Submission strategy: `.queue` (default) enqueues the task if it cannot start immediately; `.fail` makes submission fail immediately if it cannot start now, giving your app instant feedback so it can react in the foreground.

Background GPU access: add the Background GPU Access capability, then **query `supportedResources` at runtime** before requesting `.gpu` - the system rejects a submission that requests an unsupported resource.

Quality of service: background work gets lower QoS than foreground, but the system **boosts the task's priority when the app returns to the foreground**.

If the user **swipes the app away** in the App Switcher while a continued-processing task runs, the system cancels the task and the app gets **no** cancellation callback.

```swift
import BackgroundTasks

let exportID = "com.example.myapp.export" // in BGTaskSchedulerPermittedIdentifiers

// Register dynamically when the user taps "Export" (NOT required at launch):
func startExport() {
    BGTaskScheduler.shared.register(forTaskWithIdentifier: exportID, using: nil) { task in
        guard let task = task as? BGContinuedProcessingTask else { return }
        var didExpire = false
        task.expirationHandler = { didExpire = true }   // flip a flag, stop gracefully

        let progress = task.progress
        progress.totalUnitCount = 100
        while progress.completedUnitCount < 100 && !didExpire {
            performNextExportChunk()
            progress.completedUnitCount += 1
            task.updateTitle(task.title,
                             subtitle: "Completed \(Int(progress.fractionCompleted * 100))%")
        }
        task.setTaskCompleted(success: progress.completedUnitCount == 100)  // exactly once
    }

    let request = BGContinuedProcessingTaskRequest(
        identifier: exportID, title: "Exporting video", subtitle: "Preparing...")
    request.strategy = .queue
    if BGTaskScheduler.supportedResources.contains(.gpu) {
        request.requiredResources = .gpu      // needs Background GPU Access capability
    }
    do { try BGTaskScheduler.shared.submit(request) } catch { print("Submit failed: \(error)") }
}
```

## Errors (`BGTaskScheduler.Error.Code`)

- `.notPermitted` - identifier not in the plist, or an unsupported resource was requested.
- `.tooManyPendingTaskRequests` - exceeded the 1-refresh / 10-processing limit.
- `.unavailable` - the app cannot schedule background work (e.g. Background App Refresh disabled).
- `.immediateRunIneligible` - a request meant to run immediately could not, due to conditions.

## Availability

- `BGTaskScheduler`, `BGAppRefreshTask(Request)`, `BGProcessingTask(Request)`: iOS/iPadOS 13+, tvOS 13+, visionOS 1+, Mac Catalyst 13.1+, watchOS 26+.
- `BGHealthResearchTask(Request)`: iOS 17+ (no tvOS).
- `BGContinuedProcessingTask` and its request/`Resources`/`SubmissionStrategy`, plus `supportedResources`: iOS/iPadOS 26+ (no tvOS/visionOS). tvOS supports refresh/processing but not continued-processing or health-research.

SwiftUI offers the handler side of refresh and URLSession tasks via the `.backgroundTask` scene modifier - see `swiftui-background-tasks.md`. You still schedule with `BGTaskScheduler.submit`.

Test scheduled tasks on a real device with the lldb simulate commands in `testing-and-debugging.md`.
