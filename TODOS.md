# TODOs

## Still open
- check if the media layer keys in actual osx/ios are done by detecting fn+function key, or if the respective keyboards emit other hid's; if the former, we can do 'do not disturb' as just fn+f6 assuming the system is set to treat function keys as function keys and not media keys.
## Done
- [x] Nav + Num activates a MEDIA layer (conditional layer) with MacBook F-key
      shortcuts: F1→BriDn, F2→BriUp, F7→Prev, F8→Play, F9→Next, F10→Mute,
      F11→VolDn, F12→VolUp. Rendered as `br` annotations on the base overlay
      (hidden from base.svg layer sections). MDI icons added for brightness,
      media prev/play/next.
- [x] Compose key (`K_APP`) on RB5 (was ESC). Rendered with compose symbol ⎄
      (U+2384) via `{{class:sym}}⎄`.
- [x] Shifted actions for `` ` , . / ' `` rendered on keymap overlay
      (shifted in tap position, base in hold position). Post-processed in
      generate-keymaps.rb via SHIFTED_PAIRS map.
- [x] Added `!` as the Q+A vertical combo (`LT4 LM4`, slow timing).
- [x] OS mode indicator (AP/LI/IO) drawn on the Nice!View LCD display between
      the BLE/USB text and bluetooth profile dots. Reads
      `toucan_text_mode_get_current()` at draw time in `output.c`.
- [x] add symbols on the RIGHT middle location for the greek leader layer, using pastel red (#ff9b9b) as color via the `greek-anno` CSS class. make sure to avoid repetion in draw/config.yaml (there should be one place where the color for the greek colors is defined). make sure ./draw-keymap.sh runs.
