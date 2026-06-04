# Human Interface Guidelines

## Constraints and Goals
The Toucan Keyboard aims to provide a seamless hybrid experience, blending standard typing with advanced pointing capabilities through the integrated touchpad. To achieve this, the keymap and layer design must carefully balance access to typical modifiers with the specialized requirements of emitting mouse events.

### The PAD Layer Mechanism
When the user touches the right touchpad, the firmware's state machine automatically transitions the keyboard into the **PAD layer** (`layer 3`). This allows the keyboard to reinterpret key presses based on the context that the user is actively pointing.

**Crucial Constraint:** Because the PAD layer is placed above the BASE layer, it shadows the normal keymap. If a key is bound to a specific character on the PAD layer, pressing it while touching the pad will emit that character. 

To efficiently output necessary key and mouse combinations (e.g., `Shift + Click`, `Ctrl + Click`), the PAD layer **must** employ transparency (`___` or `&trans`) for modifier keys. This allows the modifiers from the BASE layer (typically Homerow Mods) to "fall through" and be recognized alongside the mouse events.

## Design Guidelines

1. **Homerow Modifiers Transparency:**
   The keys corresponding to Homerow Mods (GUI, ALT, SHIFT, CTRL) on both the left and right halves must be transparent (`___`) in the PAD layer. This allows the user to hold a modifier while dragging or clicking.

2. **Dedicated Mouse Clicks (If Gestures are Disabled):**
   If gestures (like tap-to-click) are disabled because they are too prone to accidental triggering, the user must have physical buttons readily available to perform left, middle, and right clicks. 
   - **Placement:** The most ergonomic placement for these buttons while the right hand is operating the touchpad is the **left thumb cluster**. 
   - **Configuration:** The PAD layer should bind `&mkp LCLK`, `&mkp MCLK`, and `&mkp RCLK` to the left thumb keys. This allows the right hand to point and the left hand to click simultaneously.

3. **Navigation and Panning:**
   The PAN layer is designed for scroll generation. This is bound to a thumb key on the right half. When the user rests their thumb on this key and moves their index finger on the pad, the movement translates to scrolling. The PAN activation key should ideally be placed on the rightmost thumb cluster key of the right half, ensuring a comfortable resting position for the thumb while the other fingers interact with the pad.

4. **Escaping the PAD Layer:**
   Since the PAD layer is automatically engaged via `BTN_TOUCH`, there is a slight timeout before it deactivates after lifting the finger. Keys that need to be accessible immediately after pointing (like `Enter`, `Space`, or `Backspace`) should ideally be transparent on the PAD layer so they can be triggered without waiting for the timeout.

## Summary of Layer Priorities
- **BASE Layer:** General typing, Homerow Mods.
- **PAD Layer:** Transparent modifiers, Left Thumb Clicks, Right Thumb Panning.
- **PAN Layer:** Absolute transparency; XY movement is intercepted by the firmware and converted to scroll events.
