# Testing, debugging, and system constraints

Background work runs on the system's schedule, which can be hours away and depends on conditions you do not control. You cannot wait it out during development, and you cannot test it meaningfully in the Simulator. This file covers how to force tasks to run, how to read the states that gate them, and what to design around.

## Simulating BGTaskScheduler launch and expiration

Apple ships two **private** debugger functions to force-launch and force-expire a scheduled task. They work **only on a physical device** (not the Simulator), only at a paused breakpoint, and **any reference to them in a shipping build is grounds for App Store rejection** - strip them before archiving.

### Force a launch

1. Set a breakpoint **after** a successful `submit(_:)`.
2. Run on a device until it pauses.
3. In the lldb console, run (replace the identifier):
   ```
   e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.example.myapp.refresh"]
   ```
4. Resume. The system invokes the task's launch handler.

### Force an expiration

1. Set a breakpoint **inside** the running task.
2. Force a launch with the command above; let it pause at the in-task breakpoint.
3. In lldb, run:
   ```
   e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateExpirationForTaskWithIdentifier:@"com.example.myapp.refresh"]
   ```
4. Resume. The system invokes the task's expiration handler.

`-l objc` selects Objective-C for the expression; `(void)` discards the return so lldb does not try to print it. **Always test expiration** - confirm the handler cancels work and calls `setTaskCompleted(success:)` quickly; the system can fire it at any time.

### Preconditions for the launch to fire at all

- Background Modes enabled: "Background fetch" for refresh, "Background processing" for processing.
- Every identifier in `BGTaskSchedulerPermittedIdentifiers`.
- All `register(...)` calls complete before launch finishes.

### Observing

- Use Console.app (device attached) or `log stream`, filtering the BackgroundTasks / `com.apple.duetactivityscheduler` subsystems, to watch scheduling decisions.
- Inspect what is queued at runtime with `BGTaskScheduler.shared.getPendingTaskRequests { print($0) }`.

## States that gate background work

Read and respect these; do not assume background work runs.

### Background App Refresh authorization

```swift
switch UIApplication.shared.backgroundRefreshStatus {   // iOS 7+, tvOS 11+
case .available:  break                  // proceed
case .denied:     break                  // user turned it off; offer a foreground fallback
case .restricted: break                  // parental controls / MDM - do NOT nag; they cannot change it
@unknown default: break
}
```

Subscribe to `UIApplication.backgroundRefreshStatusDidChangeNotification`. Background App Refresh is **automatically disabled in Low Power Mode**.

### Low Power Mode

```swift
if ProcessInfo.processInfo.isLowPowerModeEnabled { /* defer discretionary work */ }
```

Observe `Notification.Name.NSProcessInfoPowerStateDidChange`. Low Power Mode reduces CPU/GPU, pauses discretionary and background activity, and disables Background App Refresh. iOS 9+, macOS 12+.

### Thermal state

```swift
switch ProcessInfo.processInfo.thermalState {   // iOS 11+, macOS 10.10.3+
case .nominal:  break                 // full work
case .fair:     break                 // start trimming non-essential work
case .serious:  break                 // significantly reduce CPU/GPU; pause heavy background work
case .critical: break                 // stop all but essential work
@unknown default: break
}
```

Observe `ProcessInfo.thermalStateDidChangeNotification`. Test with Xcode's thermal-state override (Debug -> Simulate -> ... or the Devices window).

## What governs whether and when work runs

- **Device usage learning.** The system schedules `BGAppRefreshTask` around when the user typically opens the app; `earliestBeginDate` is a floor, not a promise. Per-identifier run history refines future scheduling, so cooperative apps are favored.
- **Battery / charging / idle.** Processing tasks tend to run when the device is charging and idle; `requiresExternalPower` and `requiresNetworkConnectivity` make that explicit.
- **Low Power Mode, thermal state, network availability, CPU load** all feed scheduling. Conditions being wrong can postpone even a well-formed task.
- **Force-quit.** A user swipe-killing the app suppresses `BGTaskScheduler` launches, silent push, and background `URLSession` relaunches until the next manual launch. (`fundamentals.md`.)

## Design rules that follow

- **Test on a real device.** The Simulator does not run the scheduling heuristics and does not support the private simulate functions.
- **Test the expiration path**, not just the happy path.
- **Never put correctness-critical logic solely in a background task.** Treat every background opportunity as a bonus; have a foreground path that reconciles state.
- **Save incremental progress** so an expired task resumes cheaply next time.
- **Degrade gracefully** when `backgroundRefreshStatus` is `.denied`, and stay quiet when it is `.restricted`.
- **Back off** under Low Power Mode and elevated thermal state.
