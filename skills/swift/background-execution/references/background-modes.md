# Background modes (UIBackgroundModes)

Some background work is granted by declaring a **capability** rather than scheduling a task. Background modes live in the `UIBackgroundModes` array in `Info.plist`; add them via Xcode -> target -> Signing and Capabilities -> + Capability -> Background Modes, then check the modes you need.

> The Background Modes capability is **not available for macOS apps**. For watchOS, add it to the appropriate watch target.

> **Use modes sparingly.** Apple: "If an alternative to executing in the background exists, use the alternative instead." Declaring modes you cannot justify draws App Review scrutiny and rejection (e.g. requesting continuous `location` when significant-change monitoring would do).

## The matrix

| Xcode label | `UIBackgroundModes` value | Grants | Platforms |
|---|---|---|---|
| Audio, AirPlay, and Picture in Picture | `audio` | Play audible content in background; AirPlay; PiP | iOS, tvOS, visionOS, watchOS |
| Location updates | `location` | Standard location service in background | iOS, watchOS |
| Voice over IP | `voip` | VoIP services (use with CallKit) | iOS, visionOS, watchOS |
| External accessory communication | `external-accessory` | Talk to an ExternalAccessory device delivering data at intervals | iOS |
| Uses Bluetooth LE accessories | `bluetooth-central` | Core Bluetooth central role in background | iOS, visionOS |
| Acts as a Bluetooth LE accessory | `bluetooth-peripheral` | Core Bluetooth peripheral role in background | iOS |
| Background fetch | `fetch` | Fetch content at intervals (now via `BGAppRefreshTask`) | iOS, tvOS, visionOS |
| Remote notifications | `remote-notification` | Silent/background push (`content-available`) | iOS, tvOS, visionOS, watchOS |
| Background processing | `processing` | `BGProcessingTask` scheduled work | iOS, tvOS, visionOS |
| Workout processing | `workout-processing` | Track activity via a watch workout session | watchOS |
| Uses Nearby Interaction | `nearby-interaction` | NearbyInteraction in background | iOS |
| Push to Talk | `push-to-talk` | Launch on push and play audio (PushToTalk framework) | iOS |

`fetch` and `processing` are covered in `bg-task-scheduler.md`; `remote-notification` and `voip` in `background-push.md`. The rest follow.

## Background location

```swift
var allowsBackgroundLocationUpdates: Bool   // CLLocationManager, iOS 9+, default false
```

- Requires `location` in `UIBackgroundModes`. **Setting `allowsBackgroundLocationUpdates = true` without the `location` mode is a fatal error that terminates the app.**
- With it `true` and `startUpdatingLocation()` called, Core Location keeps the app running for continuous updates after backgrounding.
- **Prefer the significant-change service** where possible - it is battery-friendly and **relaunches a terminated app** on a new event:
  ```swift
  locationManager.startMonitoringSignificantLocationChanges()
  ```
  On relaunch, the launch options contain `UIApplication.LaunchOptionsKey.location`; recreate the location manager and call the method again to keep receiving events. Expect events no sooner than ~500 m of movement and at most about every 5 minutes. Region monitoring (`startMonitoring(for:)`) behaves similarly - it wakes/relaunches on enter/exit.
- `showsBackgroundLocationIndicator` (iOS 11+) controls the blue indicator for **Always**-authorized apps. **When In Use** apps always get the indicator automatically when location is used in background.
- Authorization: unattended background use (geofences / significant-change waking a terminated app) needs **Always**. **When In Use** supports background continuation only while an update session is running with `allowsBackgroundLocationUpdates = true`. Add the `NSLocation*UsageDescription` purpose strings.

## Background audio

The `audio` mode keeps the app running for playback or microphone capture, but only alongside an **active** `AVAudioSession` with a background-capable category - the mode alone is not enough. Background audio is deep enough (categories, recording while locked, interruptions, route changes, mic permission) to have its own file: see `background-audio.md`.

## Bluetooth, external accessory, nearby interaction, push-to-talk

- `bluetooth-central` / `bluetooth-peripheral` let a Core Bluetooth app keep a BLE connection alive in the background (central or peripheral role). State preservation/restoration lets the system relaunch the app for Bluetooth events.
- `external-accessory` keeps an ExternalAccessory session alive for hardware that streams data at intervals.
- `nearby-interaction` allows NearbyInteraction ranging in background.
- `push-to-talk` (PushToTalk framework) launches the app on a PTT push and plays audio.

These are niche; reach for them only with concrete hardware/protocol requirements, and expect App Review to ask why.

## Deprecated background fetch

The legacy fetch path is **deprecated; use `BGAppRefreshTask`** (`bg-task-scheduler.md`):

```swift
// Deprecated - do not use in new code:
func application(_:performFetchWithCompletionHandler:)
UIApplication.shared.setMinimumBackgroundFetchInterval(_:)
```

Adding `BGTaskSchedulerPermittedIdentifiers` to `Info.plist` disables this old path entirely.
