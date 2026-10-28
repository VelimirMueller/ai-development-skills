# Background URLSession

A session created with `URLSessionConfiguration.background(withIdentifier:)` hands transfers to a separate system process (`nsurlsessiond`). The transfers **continue while the app is suspended or terminated**, and the system **relaunches the app in the background** when they finish. This is the right tool for large or long downloads/uploads that must survive the app leaving the foreground - not a task assertion (`task-assertions.md`).

Availability: iOS 8+, macOS 10.10+, tvOS 9+, watchOS 2+, visionOS 1+. On watchOS, all background network requests must go through a background `URLSession`.

> **Force-quit caveat:** if the user force-quits the app, the system **cancels all background transfers** and will **not** auto-relaunch the app. See `fundamentals.md`.

## Configuration

```swift
private lazy var session: URLSession = {
    let config = URLSessionConfiguration.background(withIdentifier: "com.example.myapp.bg")
    config.isDiscretionary = false          // see below
    config.sessionSendsLaunchEvents = true  // relaunch the app on completion
    config.timeoutIntervalForResource = 60 * 60 * 24 * 3   // allow up to 3 days
    return URLSession(configuration: config, delegate: self, delegateQueue: nil)
}()
```

- The `identifier` must be **non-empty and stable**. Use a fixed string literal - you must reproduce it exactly at relaunch.
- **Exactly one `URLSession` per identifier.** Build it once and store it. Creating a second live session with the same identifier is unsupported. At relaunch you create it again only because the previous process is gone.
- A background session **requires a delegate**. You cannot use completion-handler convenience methods (they need the closure to still be in memory, which is not guaranteed across relaunch). Create tasks with the non-completion factory methods (`downloadTask(with:)`, `downloadTask(withResumeData:)`, file-based `uploadTask(with:fromFile:)`) and receive results via delegate callbacks.

## The relaunch flow (the part everyone gets wrong)

When a transfer finishes while the app is suspended or terminated and `sessionSendsLaunchEvents == true`, the system wakes/relaunches the app and drives this sequence:

1. The system calls the app delegate:
   ```swift
   func application(_ application: UIApplication,
                    handleEventsForBackgroundURLSession identifier: String,
                    completionHandler: @escaping () -> Void) {
       backgroundCompletionHandler = completionHandler   // STORE it; do NOT call it yet
       BackgroundDownloadManager.shared.activate()       // recreate the session with the same id
   }
   ```
2. **Store** the `completionHandler`. Do not call it here.
3. **Recreate the background session with the same identifier and config** (if the app was freshly launched). The recreated session reattaches to the in-flight transfers and replays pending delegate callbacks. If the app was only suspended and the session object still exists, you do not need to recreate it.
4. Delegate callbacks fire (`didFinishDownloadingTo`, `didCompleteWithError`, ...).
5. When all queued events are delivered, the system calls `urlSessionDidFinishEvents(forBackgroundURLSession:)`.
6. There, call the stored handler **on the main thread** (it is a UIKit handler; calling it lets UIKit take a fresh App Switcher snapshot):
   ```swift
   func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
       DispatchQueue.main.async {
           guard let appDelegate = UIApplication.shared.delegate as? AppDelegate,
                 let handler = appDelegate.backgroundCompletionHandler else { return }
           appDelegate.backgroundCompletionHandler = nil
           handler()
       }
   }
   ```

Failing to call the handler - or calling it before events finish, or off the main thread - is the most common background-session bug; the system penalizes apps that do not call it promptly.

## Configuration knobs

| Property | Behavior |
|---|---|
| `isDiscretionary` | Lets the system pick the optimal time (power + Wi-Fi). Honored only for transfers **started in the foreground**; any transfer **started while backgrounded is treated as discretionary regardless**. Default `false`. |
| `sessionSendsLaunchEvents` | `true` (default) wakes/relaunches the app on completion and calls `handleEventsForBackgroundURLSession`. |
| `waitsForConnectivity` | **Ignored by background sessions - they always wait for connectivity.** |
| `timeoutIntervalForResource` | Max wall-clock for the entire transfer. **Default 7 days** - background transfers can legitimately run for days. |
| `allowsCellularAccess` | Default `true`; `false` blocks cellular. |
| `allowsExpensiveNetworkAccess` | iOS 13+. `false` blocks cellular / hotspot. |
| `allowsConstrainedNetworkAccess` | iOS 13+. Honors the user's Low Data Mode. Prefer gating on this. |

Per-task hints (feed discretionary scheduling - Apple strongly encourages setting them):

```swift
let task = session.downloadTask(with: url)
task.countOfBytesClientExpectsToSend = 200
task.countOfBytesClientExpectsToReceive = expectedBytes
task.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60)  // optional floor
task.resume()
```

## Constraints (background sessions only)

- **Delegate mandatory**; no completion-handler convenience APIs.
- **HTTP and HTTPS only** - no custom URL protocols.
- **Redirects are always followed** - `urlSession(_:task:willPerformHTTPRedirection:...)` is **not** called.
- **Uploads must be file-backed** (`uploadTask(with:fromFile:)`). Data- and stream-based uploads fail after the app exits.
- The temp file passed to `didFinishDownloadingTo` is valid **only until that method returns** - move or copy it synchronously inside the callback.

## Complete download manager

```swift
import Foundation
import UIKit

final class BackgroundDownloadManager: NSObject {
    static let shared = BackgroundDownloadManager()
    static let identifier = "com.example.myapp.bgdownload"   // stable, never changes

    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.background(withIdentifier: Self.identifier)
        config.sessionSendsLaunchEvents = true
        config.timeoutIntervalForResource = 60 * 60 * 24 * 3
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }()

    private override init() { super.init() }
    func activate() { _ = session }                  // touch at launch to reattach

    func startDownload(from url: URL) {
        let task = session.downloadTask(with: url)
        task.resume()
    }
}

extension BackgroundDownloadManager: URLSessionDownloadDelegate {
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                    didFinishDownloadingTo location: URL) {
        // Move the file NOW - `location` is invalid after this returns.
        let dest = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(downloadTask.originalRequest?.url?.lastPathComponent ?? UUID().uuidString)
        try? FileManager.default.removeItem(at: dest)
        try? FileManager.default.moveItem(at: location, to: dest)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        if let error = error as NSError?,
           let resumeData = error.userInfo[NSURLSessionDownloadTaskResumeData] as? Data {
            // persist resumeData to retry later
        }
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        DispatchQueue.main.async {
            guard let appDelegate = UIApplication.shared.delegate as? AppDelegate,
                  let handler = appDelegate.backgroundCompletionHandler else { return }
            appDelegate.backgroundCompletionHandler = nil
            handler()
        }
    }
}

final class AppDelegate: UIResponder, UIApplicationDelegate {
    var backgroundCompletionHandler: (() -> Void)?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions opts: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        BackgroundDownloadManager.shared.activate()   // reattach on every launch path
        return true
    }

    func application(_ application: UIApplication,
                     handleEventsForBackgroundURLSession identifier: String,
                     completionHandler: @escaping () -> Void) {
        backgroundCompletionHandler = completionHandler
        BackgroundDownloadManager.shared.activate()
    }
}
```

## Resume data

```swift
func cancel(byProducingResumeData completionHandler: @escaping @Sendable (Data?) -> Void)
func downloadTask(withResumeData resumeData: Data) -> URLSessionDownloadTask
```

On failure, resume data is also in the error: `(error as NSError).userInfo[NSURLSessionDownloadTaskResumeData] as? Data`. A download is resumable only if: the resource is unchanged since first requested, it is an HTTP/HTTPS **GET**, the server provided `ETag`/`Last-Modified` and supports byte-range requests, and the temp file was not purged. Background-config downloads handle interruption resumption automatically; manual resume data is mainly for non-background sessions.

## Efficiency

The system rate-limits relaunches with an escalating delay. Don't serialize (start one, get relaunched, start the next) - **batch many tasks onto one session at once**. The delay resets when the user foregrounds the app.

## SwiftUI

iOS 16+ apps can use `.backgroundTask(.urlSession("identifier")) { ... }` as the relaunch entry point instead of the `AppDelegate` method - see `swiftui-background-tasks.md`. You still create and operate the background `URLSession` with a delegate; the modifier only provides the wake/launch hook.
