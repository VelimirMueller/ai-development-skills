# Background audio (playback and recording)

Audio is the one workload that can run **continuously** in the background - including capturing the microphone while the screen is locked. It is granted by a capability plus an active audio session, not by a scheduled task. This covers both directions: background **playback** (music, podcasts, audiobooks) and background **recording / dictation** (voice memos, transcription, VoIP).

## The two requirements (neither alone is enough)

1. **The `audio` `UIBackgroundMode`** in `Info.plist` (Xcode: "Audio, AirPlay, and Picture in Picture" under Background Modes). This is the entitlement.
2. **An active `AVAudioSession` with a background-capable category** (`.playback`, `.playAndRecord`, `.record`, or `.multiRoute`), activated with `setActive(true)`. This is what actually keeps the audio pipeline alive.

The default session category is `.soloAmbient`, which is silenced by the Ring/Silent switch and by screen lock - so the background mode does nothing until you change the category. There is **no separate "recording" background mode**: the single `audio` mode covers capture too; what enables background recording is an active `.record` / `.playAndRecord` session.

## Categories, modes, options

### Category (the base behavior)

| Category | Records | Background / locked playback | Notes |
|---|---|---|---|
| `.soloAmbient` (default) | no | no | Silenced by Ring/Silent and lock; interrupts other audio. |
| `.ambient` | no | no | Mixes with others; silenced by lock. |
| `.playback` | no | **yes** (with `audio` mode) | Not silenced by lock/Ring switch. The only category SharePlay supports. |
| `.record` | **yes** only | yes (with `audio` mode) | Silences nearly all other system output while active. Use `.playAndRecord` instead "unless you need to prevent any unexpected sounds." |
| `.playAndRecord` | **yes** + plays | **yes** (with `audio` mode) | The dictation / VoIP default. Continues recording when the screen locks. |

- **Background playback** -> `.playback`.
- **Background recording / dictation / VoIP** -> `.playAndRecord` (preferred; will not blanket-silence the system) or `.record` (only when you must suppress all other output).

### Mode (specialized tuning)

- `.default` - works with any category.
- `.spokenAudio` - podcasts/audiobooks; your app **pauses** (not ducks) for another app's short spoken prompt. Also good for spoken-word recording.
- `.measurement` - minimal signal processing on input/output; lower output level. Valid with playback/record/playAndRecord.
- `.voiceChat` - VoIP with `.playAndRecord`; auto-applies `.allowBluetoothHFP`.
- `.videoRecording` - record/playAndRecord only; uses the mic nearest the camera.

Setting a mode the category does not support **silently falls back to `.default`** rather than erroring.

### Category options (what each changes)

- `.mixWithOthers` - your audio mixes with other apps instead of interrupting them. Recording categories are non-mixable by default; add this to let Music keep playing while you capture.
- `.duckOthers` - lowers other apps' volume while yours plays (implies `.mixWithOthers`). Temporary use only.
- `.interruptSpokenAudioAndMixWithOthers` - mixes, but pauses apps using `.spokenAudio`; resumes them on deactivation.
- `.allowBluetoothHFP` - exposes a Bluetooth Hands-Free mic for **input**. Required to record from a BT headset (`.record` / `.playAndRecord`). Replaces the deprecated `.allowBluetooth`.
- `.allowBluetoothA2DP` - stereo Bluetooth **output** (music). Must be set explicitly for `.playAndRecord`.
- `.defaultToSpeaker` - routes output to the loudspeaker instead of the receiver, even with headphones connected. `.playAndRecord` only; resets only on a category change.
- `.allowAirPlay` - enables AirPlay output.

Setters:

```swift
func setCategory(_:)                      // category only
func setCategory(_:options:)              // category + options
func setCategory(_:mode:options:)         // category + mode + options
func setCategory(_:mode:policy:options:)  // + route-sharing policy
```

## Microphone permission

Required for any capture. Without permission, recording yields **zeroed samples (silence), not an error** - a common misdiagnosis as "the pipeline is broken."

- `Info.plist`: `NSMicrophoneUsageDescription` is mandatory; the app crashes on mic access without it.
- iOS 17+: `AVAudioApplication.requestRecordPermission()`:
  ```swift
  if await AVAudioApplication.requestRecordPermission() {
      // granted
  } else {
      // denied - route the user to Settings
  }
  ```
  Inspect state via `AVAudioApplication.shared.recordPermission` (`.undetermined` / `.granted` / `.denied`).
- Pre-iOS 17 (deprecated): `AVAudioSession.requestRecordPermission(_:)`.

## Activation timing and deactivation

- **Activate when playback/recording begins**, not at launch - deferring avoids prematurely interrupting other apps' background audio.
- **Deactivate with `.notifyOthersOnDeactivation`** so apps you interrupted can resume:
  ```swift
  try session.setActive(false, options: .notifyOthersOnDeactivation)
  ```
- Activating `.record` / `.playAndRecord` while another app hosts a call **throws `AVAudioSessionErrorInsufficientPriority`** - handle it.

## Background recording specifics

- An active `.record` / `.playAndRecord` session plus the `audio` mode keeps the **mic alive when backgrounded and when the screen locks**. The active session is what keeps the app running for audio; you do **not** need a `beginBackgroundTask` assertion just to keep capturing.
- **AVAudioEngine input taps keep running** as long as the engine runs and the session stays active and uninterrupted. What stops capture is an **interruption** (call/alarm), a **route loss**, or the system muting the mic - handle those explicitly (below).
- The **orange microphone indicator** appears whenever the mic is active, including in the background. It is a system privacy indicator and **cannot be suppressed**.
- iPad Smart Folio: closing the cover mutes the built-in mic in hardware and interrupts the session (reason `.builtInMicMuted`). For play-and-record sessions that should survive a hardware mic mute, set the `.overrideMutedMicrophoneInterruption` option.
- For background **processing** after recording (transcription, upload), the recording session does not cover it - use a task assertion (`task-assertions.md`) or `BGProcessingTask` (`bg-task-scheduler.md`).

## Interruption handling (required)

A call or alarm stops your audio. Without handling it you never resume.

```swift
NotificationCenter.default.addObserver(
    forName: AVAudioSession.interruptionNotification,
    object: AVAudioSession.sharedInstance(), queue: .main
) { note in
    guard let info = note.userInfo,
          let raw = info[AVAudioSessionInterruptionTypeKey] as? UInt,
          let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }

    switch type {
    case .began:
        // Pause/stop playback or recording; update UI.
    case .ended:
        // Resume ONLY if the system recommends it.
        guard let optRaw = info[AVAudioSessionInterruptionOptionKey] as? UInt else { return }
        if AVAudioSession.InterruptionOptions(rawValue: optRaw).contains(.shouldResume) {
            try? AVAudioSession.sharedInstance().setActive(true)
            // restart engine / recorder
        }
    @unknown default: break
    }
}
```

Always check `.shouldResume` before auto-resuming. For recording, `.ended` + `.shouldResume` means re-`setActive(true)` and restart the engine/recorder. The interruption reason is in `AVAudioSessionInterruptionReasonKey` (`AVAudioSession.InterruptionReason`: `.default`, `.builtInMicMuted`, `.routeDisconnected`, ...).

> The `interruptionNotification` + keys pattern still works everywhere and is what Apple's own guide shows. `InterruptionType`/`InterruptionOptions` are marked deprecated in the newest docs in favor of `AVAudioSession.didBecomeInactiveNotification` + `resumptionRecommendationNotification`; prefer those only if you target the latest OS exclusively.

## Route-change handling (required)

When the user unplugs headphones, do not blast audio into the room - pause. This is an App Review expectation.

```swift
NotificationCenter.default.addObserver(
    forName: AVAudioSession.routeChangeNotification,
    object: AVAudioSession.sharedInstance(), queue: .main
) { note in
    guard let info = note.userInfo,
          let raw = info[AVAudioSessionRouteChangeReasonKey] as? UInt,
          let reason = AVAudioSession.RouteChangeReason(rawValue: raw) else { return }

    switch reason {
    case .oldDeviceUnavailable:   // headphones unplugged
        // Pause playback.
    case .newDeviceAvailable:
        // A new output (e.g. headphones) became available.
    default: break
    }
}
```

`AVPlayer` handles this automatically; a manual `AVAudioEngine` / `AVAudioRecorder` must handle it itself. For recording, losing the input device should pause/stop and reconfigure.

## AVAudioRecorder vs AVAudioEngine + tap

- **`AVAudioRecorder`** - simple file recording. Set up settings, `record()`, observe the delegate. Lower effort; good when you just need a file.
- **`AVAudioEngine` + `installTap(onBus:bufferSize:format:)`** - live access to PCM buffers (level metering, streaming to a transcriber, format conversion). The right choice for live dictation/transcription.

```swift
let engine = AVAudioEngine()
let input = engine.inputNode
let format = input.outputFormat(forBus: 0)            // use the node's actual format
input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
    // runs on a realtime audio thread - keep it lock-light and non-blocking
}
try engine.start()
```

### Real-world gotchas (from production dictation code)

These bite in practice and are easy to get wrong:

- **Install the tap from a non-isolated context - the `DispatchQueue` here is deliberate, not a smell.** `installTap`'s closure runs on the engine's realtime audio render thread. In Swift Concurrency, a closure created inside a `@MainActor` type (an `@Observable` view model, a `@MainActor` service) **inherits `@MainActor` isolation**; when the engine then calls it off the main thread, it trips `dispatch_assert_queue_fail` and crashes. The fix has three parts, and all three matter:
  1. Do the install in a **`nonisolated` free function** (not a method on the main-actor type), so the tap closure is non-isolated.
  2. Dispatch that install onto a background queue - `DispatchQueue.global(qos: .userInitiated).async`, awaited with `withCheckedContinuation` - so it runs off the main actor.
  3. Carry the capture state to the audio thread through a **`nonisolated, @unchecked Sendable` class guarded by an `NSLock`**, never touching actor-isolated stored properties from the tap. Hop UI updates (e.g. a level meter) back with `Task { @MainActor in ... }`.

  Do **not** "simplify" this by calling `installTap` directly in the surrounding `async`/`@MainActor` code - that reintroduces the isolation inheritance and the crash. The `DispatchQueue` + `nonisolated` function is the technique, not a workaround to be removed.
- **Match the `AVAudioFile` settings to the engine's actual input format.** Hardcoding a sample rate that differs from `inputNode.outputFormat(forBus:0)` produces failed writes or garbled audio. Read the format and build the file settings from it.
- **Deactivation can stall the UI.** `engine.stop()`, `inputNode.removeTap(onBus:)`, and `setActive(false)` can block for a noticeable time (worse right after a route change). Run teardown off the main thread so the Stop button does not hang. `.notifyOthersOnDeactivation` adds synchronous cross-app notifications and can add seconds - keep it for politeness on a normal stop, but consider a plain `setActive(false)` on fast teardown/interruption paths.
- **Reuse the engine; do not re-attach nodes.** Attaching a node twice throws. Keep one engine instance, stop it rather than destroying it, and restart the same instance next time.
- **Prewarm pattern for zero-latency capture.** To make recording start instantly, some apps keep the engine running with a tap that discards buffers ("warm"), then atomically flip a guarded `isCapturing` flag (under a lock checked inside the tap) to begin writing to a file. If you do this, give the warm session an idle timeout so it does not hold the mic indefinitely, and invalidate that timeout while real capture (and any follow-on processing) is in flight.

## Generic background-recording setup

```swift
import AVFAudio

// Carries capture state to the realtime audio thread. nonisolated + lock-guarded,
// so the tap closure never reads or writes main-actor state.
private final class CaptureBox: @unchecked Sendable {
    private let lock = NSLock()
    private var file: AVAudioFile?
    func setFile(_ file: AVAudioFile?) { lock.lock(); defer { lock.unlock() }; self.file = file }
    func write(_ buffer: AVAudioPCMBuffer) {
        lock.lock(); defer { lock.unlock() }
        try? file?.write(from: buffer)
    }
}

// nonisolated FREE function: the tap closure does NOT inherit @MainActor isolation,
// so it is safe to invoke on the engine's realtime audio thread.
private nonisolated func installCaptureTap(on input: AVAudioInputNode,
                                           format: AVAudioFormat,
                                           into box: CaptureBox) {
    input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
        // Realtime audio thread: lock-light, no @MainActor access.
        box.write(buffer)
        // To drive UI (e.g. a level meter): Task { @MainActor in ... }
    }
}

@MainActor
final class AudioCaptureService {
    private let engine = AVAudioEngine()
    private let box = CaptureBox()

    func start(writingTo url: URL) async throws {
        guard await AVAudioApplication.requestRecordPermission() else { throw CaptureError.micDenied }

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .spokenAudio,
                                options: [.mixWithOthers, .allowBluetoothHFP, .defaultToSpeaker])
        try session.setActive(true)                        // activate when capture begins

        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)         // match the file to the input format
        box.setFile(try AVAudioFile(forWriting: url, settings: format.settings))

        // Install OFF the main actor via the nonisolated function. This DispatchQueue is
        // intentional - calling installTap directly here would crash on the audio thread.
        await withCheckedContinuation { cont in
            DispatchQueue.global(qos: .userInitiated).async {
                installCaptureTap(on: input, format: format, into: box)
                cont.resume()
            }
        }
        try engine.start()
        observeInterruptionsAndRouteChanges()              // see patterns above
    }

    func stop() {
        let engine = self.engine, box = self.box
        DispatchQueue.global(qos: .userInitiated).async {  // teardown off-main to avoid UI stalls
            engine.inputNode.removeTap(onBus: 0)
            engine.stop()
            box.setFile(nil)
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }
}
```

Requires: `audio` in `UIBackgroundModes`, `NSMicrophoneUsageDescription` in `Info.plist`. Continues capturing when backgrounded / locked; handle interruptions and route changes as shown above.

For instant-start capture, keep this engine + tap running with a "warm" `CaptureBox` whose file is `nil` (buffers discarded), then call `box.setFile(...)` to begin writing - flipping capture on without restarting the engine. Give the warm session an idle timeout, and suspend that timeout while real capture and any follow-on processing are in flight.

## Common mistakes

- Setting the `audio` mode but not activating a session, or using a non-recording category (`.playback`) and expecting mic input.
- Wrong category for recording - `.record` silences all other output; prefer `.playAndRecord`.
- Setting a mode the category does not support (silent fallback to `.default`).
- Not handling interruptions, or resuming unconditionally instead of checking `.shouldResume`.
- Not handling route changes (headphones unplugged) - a privacy violation and review flag.
- Deactivating without `.notifyOthersOnDeactivation`, so other apps never resume.
- Omitting `NSMicrophoneUsageDescription` (crash) or not requesting permission (silent, zeroed audio).
- Installing the tap on the main actor (realtime-thread crash), or mismatching `AVAudioFile` settings to the engine format (garbled writes).
- Activating the session at launch instead of at capture/playback start (interrupts other apps' audio).
- Expecting to hide the orange mic indicator during background recording (impossible).
