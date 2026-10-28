# Focus Visual Feedback (tvOS + macOS)

## SwiftUI ButtonStyle with @Environment(\.isFocused)

The standard pattern for custom tvOS button styles. Read focus state from environment, apply visual changes.

```swift
struct CardButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        CardButton(configuration: configuration)
    }

    struct CardButton: View {
        @Environment(\.isFocused) var isFocused
        let configuration: ButtonStyle.Configuration

        var body: some View {
            configuration.label
                .scaleEffect(isFocused ? 1.05 : 1.0)
                .shadow(radius: isFocused ? 20 : 0)
                .animation(.easeInOut(duration: 0.2), value: isFocused)
        }
    }
}
```

### Three-state button pattern (normal / focused / pressed)

```swift
struct PrimaryButtonStyle: ButtonStyle {
    struct PrimaryButton: View {
        @Environment(\.isFocused) var isFocused
        let configuration: ButtonStyle.Configuration

        var body: some View {
            configuration.label
                .background { background }
                .animation(.easeInOut, value: isFocused)
        }

        @ViewBuilder private var background: some View {
            if configuration.isPressed {
                Color(.pressedBackground)
            } else if isFocused {
                Color(.focusedBackground)
            } else {
                Color(.normalBackground)
            }
        }
    }
}
```

### Conditional focusability in ButtonStyle

```swift
struct IconButtonStyle: ButtonStyle {
    struct IconButton: View {
        @Environment(\.isEnabled) var isEnabled
        @Environment(\.isFocused) var isFocused

        var body: some View {
            content
                .opacity(isEnabled ? 1.0 : 0.3)
                .focusable(isEnabled)  // OK here — ButtonStyle inner view, not wrapping a Button
                .animation(.easeInOut, value: isFocused)
        }
    }
}
```

## FocusBorder ViewModifier

Reusable gradient border that appears on focus:

```swift
struct FocusBorder: ViewModifier {
    let isFocused: Bool
    let cornerRadius: CGFloat
    let outset: Bool

    func body(content: Content) -> some View {
        content
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .overlay {
                if isFocused {
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .strokeBorder(
                            LinearGradient(colors: [.blue, .purple],
                                         startPoint: .leading, endPoint: .trailing),
                            lineWidth: 4
                        )
                        .padding(outset ? -8 : 0)
                }
            }
            .animation(.easeInOut, value: isFocused)
    }
}

extension View {
    func focusBorder(isFocused: Bool, cornerRadius: CGFloat = 20, outset: Bool = true) -> some View {
        modifier(FocusBorder(isFocused: isFocused, cornerRadius: cornerRadius, outset: outset))
    }
}
```

## System ButtonStyles for tvOS

- `.buttonStyle(.card)` — standard raise-on-focus + parallax + shadow. Best for media cards/posters.
- `.buttonStyle(.plain)` — no visual focus feedback. Only use when providing custom styling.
- `.buttonStyle(.bordered)` — bordered button with focus highlight.

Prefer `.card` for media content — it provides parallax, shadow, and the standard tvOS "lift" feel that custom scale effects don't replicate.

## tvOS 26 / Liquid Glass

> Evidence: Apple documentation / release notes (Aug 2026) — doc-sourced, not yet production-verified.

OS 26 introduced no new focus APIs, but Liquid Glass changes what *focused* looks like:

- System controls (including `.glass` button styles and standard tab/sidebar chrome) render focus with glass treatments on tvOS 26. Custom ButtonStyles built to visually match tvOS ≤18 system focus (scale + shadow) may now look out of place next to system chrome — compare on-device before shipping.
- **Device matrix caveat:** Apple's tvOS 26 release notes state the design updates are NOT carried forward to Apple TV 4K (1st gen) and older — the same app shows pre-glass focus visuals there. Test both looks.
- `ControlSize` works on tvOS starting with tvOS 26 (`.controlSize(_:)`, environment value) — focused-control sizing can now vary by control size, which affects scale-matching math.
- The 1.13x focus scale (see the table in layout-patterns.md) is confirmed unchanged on tvOS 26 — simulator-measured 1.133x on tvOS 26.4 with the `.card` style. Re-measure on device only for pixel-critical matching.
- Apps built with the 26 SDKs also change SwiftUI-vs-UIKit **gesture priority**: SwiftUI gestures now yield to a view's existing `UIGestureRecognizer`s/`NSGestureRecognizer`s by default (previously they didn't). Use `highPriorityGesture(_:isEnabled:)` when your SwiftUI gesture must take precedence, or `simultaneousGesture(_:isEnabled:)` to run both — relevant wherever remote gestures and focus interactions coexist.

## UIKit Focus Animations

### Coordinated scale + shadow in cells

```swift
override func didUpdateFocus(in context: UIFocusUpdateContext,
                             with coordinator: UIFocusAnimationCoordinator) {
    if context.nextFocusedView === self {
        coordinator.addCoordinatedFocusingAnimations({ _ in
            self.transform = CGAffineTransform(scaleX: 1.1, y: 1.1)
            self.layer.zPosition = 1
        }, completion: nil)
        // Shadow must use CABasicAnimation
        animateShadow(to: 0.5)
    } else if context.previouslyFocusedView === self {
        coordinator.addCoordinatedUnfocusingAnimations({ _ in
            self.transform = .identity
            self.layer.zPosition = 0
        }, completion: nil)
        animateShadow(to: 0)
    }
}

private func animateShadow(to opacity: Float) {
    let anim = CABasicAnimation(keyPath: "shadowOpacity")
    anim.fromValue = layer.shadowOpacity
    anim.toValue = opacity
    anim.duration = 0.3
    layer.add(anim, forKey: "shadowOpacity")
    layer.shadowOpacity = opacity
}
```

### zPosition management

Scaled focused cells can overlap adjacent cells or section headers. Manage `layer.zPosition`:
- Set to 1 when focused (brings cell above neighbors)
- Set to 0 when unfocused
- Set headers to `layer.zPosition = -1` if cells scale behind them

### prepareForReuse cleanup

```swift
override func prepareForReuse() {
    super.prepareForReuse()
    transform = .identity
    layer.shadowOpacity = 0
    layer.zPosition = 0
    layer.removeAnimation(forKey: "shadowOpacity")
}
```

## clipsToBounds considerations

When cells scale up on focus, content clips if `clipsToBounds = true`.

- **UIKit:** set `clipsToBounds = false` on the cell AND its `contentView` (both clip independently), and leave enough inter-item spacing for the scaled frame.
- **SwiftUI:** there is no clipsToBounds toggle — avoid `.clipped()` and fixed-size ancestors around focus-scaling content, and give rows headroom (padding on the container) so the 1.13x scale isn't cut off by a scroll view edge. Raise the focused card with `.zIndex(1)` if neighbors overlap it.

## macOS Focus Ring Styling

### System Focus Ring

macOS uses a blue focus ring (system accent color) drawn by AppKit. It animates in/out automatically.

```swift
class MyView: NSView {
    override var acceptsFirstResponder: Bool { true }

    // .exterior — ring outside the view bounds (default)
    // .interior — ring inside the view bounds
    // .none — no ring (provide your own visual)
    override var focusRingType: NSFocusRingType { .exterior }
}
```

### Custom Focus Ring Shape

Default focus ring matches view bounds (rectangular). Override for non-rectangular content:

```swift
class CircularAvatarView: NSView {
    override var focusRingMaskBounds: NSRect {
        return bounds  // Region containing the mask
    }

    override func drawFocusRingMask() {
        // Ring follows this shape instead of the view's rect
        let path = NSBezierPath(ovalIn: bounds)
        path.fill()
    }

    // If content that shapes the ring changes in a way AppKit can't detect
    // (e.g., the avatar image is swapped), CALL noteFocusRingMaskChanged().
    // Resizes and needsDisplay re-evaluate the mask automatically.
    func avatarDidChange() {
        noteFocusRingMaskChanged()
    }
}
```

### Disabling Focus Ring for Custom Visuals

```swift
class CustomStyledView: NSView {
    override var focusRingType: NSFocusRingType { .none }

    override func draw(_ dirtyRect: NSRect) {
        // Draw custom focus indicator when focused
        if window?.firstResponder === self {
            NSColor.controlAccentColor.setStroke()
            let path = NSBezierPath(roundedRect: bounds.insetBy(dx: 2, dy: 2),
                                     xRadius: 6, yRadius: 6)
            path.lineWidth = 2
            path.stroke()
        }
    }

    override func becomeFirstResponder() -> Bool {
        needsDisplay = true  // Redraw with focus indicator
        return super.becomeFirstResponder()
    }

    override func resignFirstResponder() -> Bool {
        needsDisplay = true  // Redraw without focus indicator
        return super.resignFirstResponder()
    }
}
```

### SwiftUI Custom Focus Styling on macOS

```swift
struct MacCardView: View {
    @FocusState private var isFocused: Bool

    var body: some View {
        content
            .focusable()
            .focused($isFocused)
            .focusEffectDisabled()  // Hide system ring
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isFocused ? Color.accentColor : .clear, lineWidth: 2)
            )
            .shadow(color: isFocused ? .accentColor.opacity(0.3) : .clear, radius: 8)
            .animation(.easeInOut(duration: 0.15), value: isFocused)
    }
}
```

### macOS vs tvOS Focus Styling Comparison

| Aspect | tvOS | macOS |
|--------|------|-------|
| Default effect | Scale up + shadow + parallax | Blue focus ring |
| Custom via | `@Environment(\.isFocused)` in ButtonStyle | `focusRingType` + `drawFocusRingMask()` or SwiftUI `@FocusState` |
| Animation | `UIFocusAnimationCoordinator` | `needsDisplay = true` or SwiftUI `.animation` |
| System style | `.buttonStyle(.card)` | System focus ring (automatic) |
| Disable default | `.buttonStyle(.plain)` | `.focusEffectDisabled()` or `focusRingType = .none` |
