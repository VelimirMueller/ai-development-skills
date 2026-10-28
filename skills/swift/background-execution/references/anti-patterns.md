# Anti-patterns: common background-execution mistakes

Background execution is a fast-moving, heavily constrained area, and most training data predates the modern shape of it (`BGTaskScheduler`, the iOS 13 scene lifecycle, the iOS 26 continued-processing task). These are the mistakes to catch. Each has a wrong/right pair or a concrete fix.

## Model-level mistakes

### Assuming background work is guaranteed
Background execution is opportunistic and discretionary; tasks can be postponed indefinitely or never run. Never make a feature's correctness depend on a background task firing. Always have a foreground reconciliation path. (`fundamentals.md`)

### Ignoring force-quit semantics
A user force-quitting the app disables `BGTaskScheduler`, silent push, and background `URLSession` relaunch until the next manual launch. Do not design for users who habitually swipe-kill.

### Picking the wrong family
"Finish work that is already running" is a **task assertion**. "Run work later" is **`BGTaskScheduler`**. "Survive a long transfer" is a **background `URLSession`". Using a `beginBackgroundTask` assertion to start a fresh multi-minute download is the classic miscategorization - it gets ~30 s and dies.

## BGTaskScheduler

### Registering after launch, or twice
```swift
// WRONG - registering lazily / in a view; or registering the same id twice (crashes)
.onAppear { BGTaskScheduler.shared.register(forTaskWithIdentifier: id, using: nil) { ... } }
```
```swift
// CORRECT - once, before launch finishes
init() {   // App.init() or application(_:didFinishLaunchingWithOptions:)
    BGTaskScheduler.shared.register(forTaskWithIdentifier: id, using: nil) { task in ... }
}
```
The system can launch the app straight into the background; the handler must already exist. A duplicate registration of the same identifier crashes the app. (Continued-processing tasks are the documented exception - they register dynamically.)

### Forgetting to reschedule
Requests are one-shot. If the launch handler does not submit the next request, the task never recurs.
```swift
func handleAppRefresh(task: BGAppRefreshTask) {
    scheduleAppRefresh()   // FIRST line - reschedule the next occurrence
    // ... then do the work ...
}
```

### Omitting the expiration handler
Without one, the system silently marks the task complete-and-unsuccessful. With one, you must still call `setTaskCompleted(success:)` exactly once.
```swift
task.expirationHandler = { operation.cancel() }
operation.completionBlock = { task.setTaskCompleted(success: !operation.isCancelled) }
```

### Calling setTaskCompleted zero or multiple times
Zero -> the app is killed at expiry and future scheduling is penalized. Call it exactly once, on completion or in the expiration handler.

### Treating earliestBeginDate as a schedule
It is a floor only ("won't begin sooner"). Execution is opportunistic and may be hours later or never.

### Putting power/network knobs on app-refresh
`requiresExternalPower` / `requiresNetworkConnectivity` exist only on `BGProcessingTaskRequest`, not `BGAppRefreshTaskRequest`.

### Missing or mismatched plist entries
Every identifier must be in `BGTaskSchedulerPermittedIdentifiers` and the matching `UIBackgroundModes` (`fetch` / `processing`) enabled, or `register` returns `false` and `submit` throws `.notPermitted`.

### Misusing the continued-processing task (iOS 26)
It must be **user-initiated** with measurable progress. Using it for automatic maintenance, backups, or photo sync gets the task canceled. It must report progress - a task that reports none is expired. Requesting `.gpu` without first checking `BGTaskScheduler.supportedResources` (and adding the Background GPU Access capability) gets the submission rejected.

## Task assertions

### Unbalanced begin/end (guaranteed kill)
```swift
// WRONG - no end on the expiration path; app is terminated
let id = UIApplication.shared.beginBackgroundTask()
doWork()
UIApplication.shared.endBackgroundTask(id)   // never reached if time expires first
```
```swift
// CORRECT - end on BOTH paths, idempotently
var id: UIBackgroundTaskIdentifier = .invalid
func end() { guard id != .invalid else { return }
            UIApplication.shared.endBackgroundTask(id); id = .invalid }
id = UIApplication.shared.beginBackgroundTask { end() }   // expiration path
doWork { end() }                                          // success path
```

### Calling beginBackgroundTask too late
Calling it at the end of `sceneDidEnterBackground(_:)` can lose the race - the assertion is granted asynchronously and you may already be suspended. Call it before starting the work.

### Heavy work in the expiration handler
It runs synchronously on the main thread and blocks suspension. Keep it to: stop work, call `end`, reset the id.

### beginBackgroundTask in an app extension
Not allowed. Use `ProcessInfo.performExpiringActivity`, and honor its `expired` Bool (the block can run a second time with `expired == true`).

### Trusting backgroundTimeRemaining
It reads `DBL_MAX` in the foreground and is advisory in the background. Plan for ~30 s and rely on the expiration handler, not the number.

## Background URLSession

### Using completion-handler convenience methods or dataTask
Background sessions require a **delegate**; convenience completion-handler APIs and `dataTask` do not work. Use `downloadTask`/file `uploadTask` and delegate callbacks.

### More than one session per identifier
```swift
// WRONG - new session every download
func download(_ url: URL) {
    let s = URLSession(configuration: .background(withIdentifier: "bg"))  // duplicate id
    s.downloadTask(with: url).resume()
}
```
Build one session, store it, reuse it; recreate only after process relaunch with the identical identifier and config.

### Not handling the relaunch correctly
Store the handler from `handleEventsForBackgroundURLSession`, recreate the session, and call the stored handler from `urlSessionDidFinishEvents(forBackgroundURLSession:)` **on the main thread** - not from `handleEvents` directly, not off the main thread.

### Reading the downloaded file later
`didFinishDownloadingTo`'s `location` is valid only until the method returns. Move/copy it synchronously inside the callback.

### Expecting configured behavior that background overrides
Background-started transfers force `isDiscretionary = true`; background sessions always wait for connectivity (the property is ignored); the redirect delegate is never called; uploads must be file-backed.

### Serializing transfers across relaunches
The system rate-limits relaunches with an escalating delay. Batch many tasks at once instead of one-at-a-time.

## Background push

### Missing apns-push-type: background
The silent push is dropped with no client-side signal. The header is required (and `apns-priority: 5`).

### Mixing content-available with alert/sound/badge
The background `aps` dictionary must contain only `content-available`.

### Not calling the fetch completion handler
`didReceiveRemoteNotification:fetchCompletionHandler:` gives ~30 s; not calling the handler terminates the app and reduces future wakeups.

### Expecting silent push to always deliver
It is throttled (a few per hour), coalesced (only the newest held one survives), and not delivered to force-quit apps. Use an alert push or PushKit for anything time-critical.

### Not reporting a CallKit call on a VoIP push (iOS 13+)
Mandatory on every VoIP push, or the system terminates the app and revokes VoIP-push privileges. Do not use VoIP pushes for non-call data.

## Background modes

### allowsBackgroundLocationUpdates without the location mode
A fatal error that terminates the app. The `location` mode must be present.

### Background audio without an active AVAudioSession
The `audio` mode alone does not keep the app alive; you need an active `.playback` (or equivalent) session. Activating it too early needlessly interrupts other apps' audio - defer until playback begins.

### Requesting modes you cannot justify
App Review rejects unjustified modes. Prefer the lighter alternative (significant-change location over continuous `location`; `BGAppRefreshTask` over keeping the app awake).

## Background audio

### The audio mode without an active session, or the wrong category
The `audio` mode alone keeps nothing alive; you need an active `AVAudioSession` with a background-capable category. Use `.playback` for playback, `.playAndRecord` for recording while locked. `.record` silences nearly all other system output - prefer `.playAndRecord` unless you must.

### Installing an AVAudioEngine tap on the main actor (then "simplifying" the DispatchQueue away)
```swift
// WRONG - tap closure inherits @MainActor isolation, crashes on the audio thread
@MainActor func start() {
    input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
        self.write(buffer)   // dispatch_assert_queue_fail on the realtime thread
    }
}
```
```swift
// CORRECT - install via a nonisolated free function dispatched off the main actor,
// bridging state through a lock-guarded @unchecked Sendable box.
await withCheckedContinuation { cont in
    DispatchQueue.global(qos: .userInitiated).async {
        installCaptureTap(on: input, format: format, into: box)  // nonisolated
        cont.resume()
    }
}
```
The `DispatchQueue` + `nonisolated` function is the technique. Do not refactor it into a direct call inside the `async`/`@MainActor` body - that reintroduces the isolation inheritance and the crash. (See `background-audio.md`.)

### AVAudioFile settings that do not match the engine format
Hardcoding a sample rate or channel count that differs from `inputNode.outputFormat(forBus: 0)` produces failed writes or garbled audio. Build the file settings from the node's actual format.

### Not handling interruptions and route changes
A call/alarm stops capture; resume only on `.shouldResume`. Headphones unplugged (`.oldDeviceUnavailable`) must pause playback - failing to is a privacy/review issue.

### Missing mic permission or NSMicrophoneUsageDescription
No `NSMicrophoneUsageDescription` crashes on mic access; no granted permission yields silent (zeroed) samples, not an error - easy to misdiagnose as a broken pipeline.

### Deactivating without notifying others, or on the main thread
Omit `.notifyOthersOnDeactivation` and other apps never resume. Run `engine.stop()` / `removeTap` / `setActive(false)` off the main thread - they can stall and hang the UI (worst right after a route change).

## Lifecycle

### Using deprecated app-delegate callbacks while scenes are enabled
With scenes, UIKit calls `sceneDidEnterBackground(_:)`, not `applicationDidEnterBackground(_:)`. Wire up the scene delegate (or observe `UIApplication.didEnterBackgroundNotification`, which fires either way).

### Doing too much in the background-transition delegate
`sceneDidEnterBackground(_:)` has ~5 s to return; overrun terminates the app. Do quick cleanup; defer real work to an assertion or a scheduled task.

### Putting background setup in view code
A background launch may never construct the UI. Register tasks, recreate sessions, and wire dependencies on a path that runs on every launch (`App.init()` / `didFinishLaunching`), not in `.onAppear` / `.task`.

## Cross-platform

### Using performExpiringActivity on macOS
It does not exist there. Use `ProcessInfo.beginActivity` / `endActivity`.

### Leaking a beginActivity token (macOS)
Not balancing `beginActivity` with `endActivity` keeps the Mac awake / out of App Nap indefinitely. Prefer `performActivity` (auto-scoped).

### Shipping the lldb simulate functions
`_simulateLaunchForTaskWithIdentifier:` / `_simulateExpirationForTaskWithIdentifier:` are private. Any reference in a submitted build is an App Store rejection. They are device-only debugging aids.
