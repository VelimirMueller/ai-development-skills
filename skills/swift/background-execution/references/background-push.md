# Background push and PushKit / VoIP

Two push mechanisms wake the app to run in the background:

- **Background (silent) push** - the server signals that new content is available; the system wakes the app at an opportune time to fetch it.
- **PushKit / VoIP push** - delivers an incoming-call invitation and wakes/launches the app even when not running.

## Background (silent) push

A background notification shows no alert, plays no sound, sets no badge. It wakes the app in the background. Requires the **`remote-notification`** background mode (`background-modes.md`).

### Payload - only `content-available`

```json
{
  "aps": { "content-available": 1 },
  "myKey": "myValue"
}
```

The `aps` dictionary must contain **only** `content-available` and must **not** include `alert`, `sound`, or `badge` - any of those changes how the notification is handled.

### Required headers on the APNs request

- `apns-push-type: background` - **required** (required for watchOS, recommended everywhere). Missing this header is the classic cause of a silent push being silently dropped.
- `apns-priority: 5` - background pushes are low priority (use 10 only for user-facing alerts).
- `apns-topic: <bundle-id>`

### Handler

```swift
func application(_ application: UIApplication,
                 didReceiveRemoteNotification userInfo: [AnyHashable : Any],
                 fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
    Task {
        do {
            let gotNew = try await contentSync.refresh(userInfo: userInfo)
            completionHandler(gotNew ? .newData : .noData)   // call within ~30 s
        } catch {
            completionHandler(.failed)
        }
    }
}
```

- Called whether the app is foreground or background (with `remote-notification` enabled, the system launches/wakes the app into the background to call it).
- ~**30 seconds** of wall-clock time; you **must** call `completionHandler` with the best `UIBackgroundFetchResult` (`.newData` / `.noData` / `.failed`) or the app is terminated and gets fewer future wakeups.
- An `async` variant exists: `application(_:didReceiveRemoteNotification:) async -> UIBackgroundFetchResult`.
- watchOS: `WKExtensionDelegate.didReceiveRemoteNotification(_:fetchCompletionHandler:)`.

### Delivery is budgeted, not guaranteed

The system treats background pushes as **discretionary, low priority, and coalesced**:

- It may hold and delay delivery; when a newer one arrives it **discards the older held one and keeps only the newest**.
- It throttles delivery - do not send more than a few per hour.
- A power-hungry app that processes them expensively gets woken less often.
- They are **not delivered to a force-quit app**; a held push is delivered when the user next launches the app.

Never use a silent push for time-critical or guaranteed delivery. For that, use an **alert push** (`apns-push-type: alert`, `apns-priority: 10`, with `alert`/`sound`/`badge`) - delivered reliably and shown by the system even if the app is not running - or PushKit for calls.

## PushKit / VoIP

For **incoming-call invitations only**. `PKPushRegistry` (iOS 8+, macOS 10.15+, watchOS 6+, visionOS 1+); `PKPushType.voIP` (iOS 9+, watchOS 9+, visionOS 1+, Mac Catalyst 14+). VoIP payloads can be up to **5 KB** (vs 4 KB for normal pushes). Topic is `<bundle-id>.voip`. Set `apns-expiration: 0` so a stale call invite is not delivered late.

### The hard rule (iOS 13 SDK and later): every VoIP push must report a call to CallKit

If your app links against the iOS 13 SDK or later, **PushKit requires CallKit**. On **every** VoIP push you must promptly report an incoming call with `CXProvider.reportNewIncomingCall(with:update:completion:)`. If you fail to, the system **terminates the app**; repeated failures **revoke your app's VoIP-push launch privileges**. If you cannot adopt CallKit, do not use PushKit - use User Notifications (with a Notification Service Extension to decrypt content). Do not use VoIP pushes for chat, refresh, or any non-call data.

```swift
func registerForVoIPPushes() {
    voipRegistry = PKPushRegistry(queue: nil)
    voipRegistry.delegate = self
    voipRegistry.desiredPushTypes = [.voIP]    // assign LAST; this starts registration
}

func pushRegistry(_ registry: PKPushRegistry,
                  didReceiveIncomingPushWith payload: PKPushPayload,
                  for type: PKPushType,
                  completion: @escaping () -> Void) {
    guard type == .voIP else { completion(); return }
    let update = CXCallUpdate()
    update.remoteHandle = CXHandle(type: .phoneNumber, value: callerHandle)
    callProvider.reportNewIncomingCall(with: callUUID, update: update) { error in
        completion()                            // tell PushKit you are done
    }
    establishConnection(for: callUUID)          // connect to your VoIP server in parallel
}
```

Create the `CXProvider` early with a `CXProviderConfiguration`. After the initial push, exchange further call state over your own connection, not more pushes.

## APNs request shapes (server side, for reference)

```
# background (silent)
apns-push-type: background
apns-priority: 5
apns-topic: com.example.myapp
{ "aps": { "content-available": 1 } }

# alert (contrast: reliable, user-facing)
apns-push-type: alert
apns-priority: 10
apns-topic: com.example.myapp
{ "aps": { "alert": { "title": "Hi", "body": "New message" }, "sound": "default" } }

# VoIP (PushKit)
apns-push-type: voip
apns-topic: com.example.myapp.voip
apns-expiration: 0
{ "callUUID": "1B4F...", "handle": "+15551234567", "callerName": "Jane" }
```

## Common mistakes

- Omitting `apns-push-type: background` -> the silent push is dropped with no client signal.
- Expecting silent push to always deliver -> it is throttled, coalesced, and not delivered to force-quit apps.
- Putting `alert`/`sound`/`badge` next to `content-available` -> changes the handling.
- Not calling the completion handler within ~30 s -> termination and fewer future wakeups.
- Not reporting a CallKit call on every VoIP push (iOS 13+) -> termination, then loss of VoIP-push privileges.
- Using VoIP pushes for non-call data -> disallowed; use User Notifications instead.
