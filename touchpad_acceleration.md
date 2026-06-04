# Touchpad Acceleration Research

## Overview
Touchpad pointer acceleration is crucial for balancing precision (small movements) and speed (large movements crossing the screen). Without acceleration, a touchpad can feel either too sluggish when trying to reach the edges or too sensitive when trying to hit small targets.

## Implementation Options

### 1. OS-Level Acceleration
Modern operating systems (macOS, Windows, Linux/libinput) have built-in pointer acceleration curves that apply to standard HID mouse events. 
- **Pros:** Native feeling, highly tuned by the OS, requires no firmware changes.
- **Cons:** Dependent on the host OS. Custom curves are hard to port between devices.

### 2. Firmware-Level ZMK Built-ins
ZMK has a few basic input processors out of the box:
- `&zip_xy_scaler`: A simple linear scaler that multiplies `dx` and `dy` by a fixed factor. This adjusts sensitivity but does not provide dynamic acceleration based on velocity.
- `&mmv`: ZMK's mouse emulation for keyboard keys has built-in acceleration (`time-to-max-speed-ms`, `acceleration-exponent`), but this does not apply to physical pointing devices which emit raw relative events.

### 3. Firmware-Level Custom Input Processor
A custom ZMK input processor can track the velocity of the trackpad movement (distance over time) and apply a dynamic scaling factor. A community-standard module for this is `zmk-pointing-acceleration` (by oleksandrmaslov).
- **Pros:** Device-agnostic (the trackpad will feel the same on any OS). Highly customizable with parameters for `min-factor`, `max-factor`, `speed-threshold`, and `acceleration-exponent`.
- **Cons:** Requires pulling in an external Zephyr module.

## Recommendation

To achieve the goal of being able to "cross the entire screen when moving the finger at human speed fast from one side to the other" while retaining fine precision, we should implement **firmware-level acceleration using the `zmk-pointing-acceleration` module**.

This allows us to configure a quadratic acceleration curve that keeps slow movements precise (e.g., `<800>` multiplier) but ramps up significantly for fast swipes (e.g., `<3000>` multiplier).

### Recommended Configuration
```devicetree
&pointer_accel {
    input-type = <INPUT_EV_REL>;
    min-factor = <800>;        // Slight slowdown for precision
    max-factor = <3000>;       // Good acceleration for large movements
    speed-threshold = <1200>;  // Balanced acceleration point
    speed-max = <6000>;
    acceleration-exponent = <2>; // Smooth quadratic curve
    track-remainders;         // Track fractional movements
};
```
This configuration will be injected into the `input-processors` array of the trackpad's listener.

## Comparison to MacBook Trackpads

A MacBook trackpad is widely considered the gold standard for pointing devices. Achieving parity with it using a custom ZMK keyboard involves several factors:

### Pointer Movement
- **MacBook:** Highly tuned proprietary acceleration curves, high polling rate, and deep OS integration. It uses velocity, acceleration, and contact area to filter out noise and precisely map finger movement to the screen.
- **ZMK with `zmk-pointing-acceleration`:** We can get *very close* to the fundamental feel of MacBook pointer movement. By tracking fractional remainders (`track-remainders;`) and using a quadratic curve (`acceleration-exponent = <2>`), ZMK firmware accurately replicates the "slow is precise, fast is accelerated" behavior. However, because it emulates a standard USB/Bluetooth mouse rather than a native Apple trackpad device, macOS applies its own secondary mouse acceleration on top of it. For the most 1:1 feel, users often use a third-party tool like LinearMouse on macOS to disable the OS's artificial mouse acceleration, allowing the firmware's pure acceleration curve to shine.

### Smooth Scrolling
- **MacBook:** Generates high-resolution, pixel-perfect scroll events (`NSEventTypeScrollWheel` with precise `deltaX`/`deltaY` values). It supports inertial scrolling, rubber-banding, and zooming.
- **ZMK Firmware:** Standard ZMK scroll events emit traditional detented "wheel clicks" (`INPUT_REL_WHEEL`), not high-resolution smooth scroll events. As a result, scrolling will feel more like turning a physical mouse wheel rather than swiping a smartphone screen. While we can increase the `wheel-clicks` resolution in the Pinnacle driver to make it feel smoother, it will not support native macOS inertial scrolling out-of-the-box unless the host OS translates high-frequency wheel clicks into smooth scrolling (which macOS does reasonably well, though it lacks the perfect elasticity of the native trackpad). Workarounds exist on the host side (like Mac Mouse Fix or MOS) that interpolate standard scroll events into smooth, inertial scrolling, bridging the gap significantly.
