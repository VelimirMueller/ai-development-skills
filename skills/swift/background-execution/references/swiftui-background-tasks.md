# SwiftUI background tasks

SwiftUI exposes two things: `ScenePhase` for **observing** the lifecycle, and the `.backgroundTask` scene modifier for **handling** scheduled background work with async/await. Neither replaces scheduling - you still submit `BGTaskScheduler` requests and configure background `URLSession`s.

## ScenePhase

```swift
@main
struct MyApp: App {
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup { RootView() }
            .onChange(of: scenePhase) {
                if scenePhase == .background {
                    // Free resources, save state - expect termination soon after.
                }
            }
    }
}
```

`.active` / `.inactive` / `.background`. Read from a `View` it reflects that scene; read from `App` it is an aggregate (`.active` if any scene is active). `ScenePhase` only observes - it grants no background runtime. iOS 14+, macOS 11+, watchOS 7+, tvOS 14+.

## The .backgroundTask scene modifier

```swift
nonisolated func backgroundTask<D, R>(
    _ task: BackgroundTask<D, R>,
    action: @escaping @Sendable (D) async -> R
) -> some Scene where D : Sendable, R : Sendable
```

iOS 16+, macOS 13+, watchOS 9+, tvOS 16+, visionOS 1+. Task types include:

- `.appRefresh("identifier")` -> `BackgroundTask<Void, Void>` - the handler side of `BGAppRefreshTask`.
- `.urlSession("identifier")` -> the handler side of a background `URLSession` completion.

This is the **handler**, not the scheduler. You still schedule the refresh with `BGTaskScheduler.shared.submit(BGAppRefreshTaskRequest(...))`, and the handler runs when that scheduled wake fires - matched by an **identical identifier string** in the request and the modifier. A mismatch means the handler never runs.

Completion and expiration are async/await native: the system considers the task complete when the `action` closure **returns**. If runtime expires first, the system **cancels the Swift Task** (standard cooperative cancellation). Observe it with `withTaskCancellationHandler` and, in the `onCancel` block, promote in-flight work to a background `URLSession` download so it survives suspension.

```swift
@main
struct WeatherApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }

        // Handler for the scheduled refresh:
        .backgroundTask(.appRefresh("com.example.weather.refresh")) {
            await scheduleNextRefresh()           // reschedule the next wake
            if await isStormy() {
                await notifyUser()
            }
        }

        // Handler invoked when a background transfer completes:
        .backgroundTask(.urlSession("com.example.weather.bg")) {
            // process the completed download
        }
    }
}

func isStormy() async -> Bool {
    let config = URLSessionConfiguration.background(withIdentifier: "com.example.weather.bg")
    config.sessionSendsLaunchEvents = true
    let session = URLSession(configuration: config)
    return await withTaskCancellationHandler {
        let (data, _) = try! await session.data(for: request)
        return parseIsStormy(data)
    } onCancel: {
        // Runtime expiring: hand off to a background download that persists past suspension.
        session.downloadTask(with: request).resume()
    }
}
```

> On **watchOS**, all background network requests must go through a background `URLSession`.

## Scheduling the request (still required)

The modifier does not schedule anything. Submit the request from app code - typically when entering the background:

```swift
func scheduleNextRefresh() {
    let request = BGAppRefreshTaskRequest(identifier: "com.example.weather.refresh")
    request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60)
    try? BGTaskScheduler.shared.submit(request)
}
```

The identifier must also be in `BGTaskSchedulerPermittedIdentifiers` and the matching `UIBackgroundModes` (`fetch`) enabled - see `bg-task-scheduler.md`.

## Testing it

The `.backgroundTask` handler runs on the system's schedule, which is opportunistic and may be hours away. To trigger it during development, use the lldb simulate-launch command against the same identifier on a real device - see `testing-and-debugging.md`. The closure-based, async nature also makes the body unit-testable in isolation: factor the work into a plain `async` function and call it directly from a test, separate from the scene wiring.

## When to use which

- Pure SwiftUI app, simple refresh / URLSession handling -> `.backgroundTask`. Less boilerplate than an `AppDelegate`.
- Need `BGProcessingTask`, `BGContinuedProcessingTask`, fine-grained control, or `handleEventsForBackgroundURLSession` plumbing -> use `BGTaskScheduler` / the `AppDelegate` directly (`bg-task-scheduler.md`, `background-url-session.md`). You can mix: a SwiftUI app can still adopt `UIApplicationDelegateAdaptor` for the URLSession relaunch handler.
