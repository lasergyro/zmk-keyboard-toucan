# Homerow mods vs. combos (2026-07-13)

## Symptoms

1. Holding the right-hand SHIFT+GUI homerow keys (`J`+`K`) emitted a repeating `(` instead of holding both modifiers.
2. Repeatedly holding and releasing the left GUI+SHIFT pair (`D`+`F`) registered only the first press; everything afterwards was silent.

## Root cause

One bug, two faces. ZMK's combo listener captures raw key-position events *before* the keymap is consulted, so a combo always beats a hold-tap. Every adjacent homerow-mod pair also happened to be a combo:

| Positions | Keys | Modifiers | Combo it fired |
|-----------|------|-----------|----------------|
| LM3 LM2 | `S`+`D` | LALT+LGUI | `tab` (`LS(LA(TAB))`) |
| LM2 LM1 | `D`+`F` | LGUI+LSHFT | `german_ns` (leader) |
| RM1 RM2 | `J`+`K` | RSHFT+RGUI | `lpar` (`(`) |
| RM2 RM3 | `K`+`L` | RGUI+RALT | `rpar` (`)`) |

Holding the pair held the combo's keycode, which the host then auto-repeated (symptom 1). On the left, `D`+`F` fires the *German namespace leader*, which has no timeout and consumes every subsequent keystroke — so repeats produced nothing at all (symptom 2).

Confirmed on hardware before the fix (`P,<delay>,<pos>,<val>` injection, HID capture):

```
JK x3 gap=300ms : LSFTv 0x26v LSFT^ 0x26^  (x3)   # `(` held, not RSHFT+RGUI
SD x3 gap=300ms : LSFTv LALTv 0x2bv ...    (x3)   # ALT+SHIFT+TAB held
DF x3 gap=300ms : (nothing)                       # leader swallowed everything
```

## Fix

**Combos on modifier pairs became hold-taps** (`config/combos.dtsi`): tap → the original combo, hold → both modifiers, held as explicit `&kp` presses via a macro (implicit mods are cleared on the next key release, so they cannot be used for held modifiers).

**Homerow keys became mod-morphs keyed on the opposite hand's modifiers** (`config/toucan.keymap`): while the other hand holds modifiers, a homerow key is a plain tap. This makes press order decide what is a modifier — mods first, then keys — and means a held opposite-hand key repeats its letter instead of resolving to its modifier. Stock hold-taps cannot express this: `decide_positional_hold()` only vetoes a hold when another key was pressed *after* the hold-tap, so a lone held homerow key always resolves to its modifier on timer expiry.

Same-hand chords are untouched: a left homerow key never morphs on left-hand modifiers.

## Why 3-modifier chords still work

`A`+`S`+`D` looked like it should break (`S`+`D` is the `tab` combo, and ZMK drops a hold-tap press while another hold-tap is undecided). It works because rule 1 of the resolution chain saves it: while `A` is undecided it parks the `S` and `D` events, so the combo is not evaluated until `A` has resolved to CTRL and `undecided_hold_tap` is clear. Measured: `LCTL LALT LGUI` held. ✓

## Remaining rough edges (candidates for simplification)

### 1. Same-hand mod + key (fixed for every reachable-by-typing case)

Requirement: a same-hand homerow key + key must never mean modifier + key.

Two distinct paths produced it:

- **Undecided mod.** `hold-trigger-on-release` only recorded the vetoing key on its *release*, so a homerow key held past its 280 ms term resolved to its modifier before any veto could run (`hold D 250ms, press C` → `Cmd+C`). Fixed by dropping `hold-trigger-on-release` and whitelisting the same-hand homerow-mod positions in `hold-trigger-key-positions`, which keeps same-hand *modifier chords* working while letting any other same-hand key veto at press time. Measured after the fix — 130, 200, 250 and 275 ms gaps all give `dc`.

- **Already-resolved mod.** Holding `D` alone for >280 ms makes it GUI; a later `C` is `Cmd+C` and no hold-tap veto can retract it. **Accepted (option a).** Only a deliberate lone hold reaches it; no typing-speed sequence does. Suppressing it via mod-morph is *unsound*: `zmk_hid_masked_modifiers_set()` writes a single global and `on_mod_morph_binding_released()` clears it unconditionally, so with two same-hand keys held (`C` then `V`) the first release unmasks the modifier and the host sees `Cmd+V`. A correct version would need a custom behavior that recomputes the mask from all held keys — and it would share that global with the existing shift morphs (`comma_morph`, `dot_morph`, `qmark_morph`, `sqt_morph`, `lpar_lt`, `rpar_gt`). Not worth it for a deliberate-only path; kept as an escape hatch.

Separately, the vertical combos still shadow the homerow columns below ~120 ms (`D`+`C` → `\`, `S`+`X` → `` ` ``, `F`+`V` → `=`). Moving them off the homerow columns would remove one of the four meanings each homerow key carries.

### 2. Four meanings per homerow key

Each homerow key is now a letter, a modifier, a horizontal-combo half, and a vertical-combo half — discriminated purely by timing. The fix makes the modifier cases correct but does not reduce the count.

*Options:* (a) accept; (b) move the four two-mod combos (`tab`, `german`, `lpar`, `rpar`) off the homerow pairs entirely, which drops the hold-tap wrappers added here and makes modifier chords unconditional; (c) status quo.

### 3. Combos ignore the order rule

Under held modifiers, a combo is still a combo (`CTRL+ALT` + hold `J`+`K` → `CTRL+ALT+SHIFT+GUI`, not `ctrl+alt+jk`). Tapping works as expected (`CTRL+ALT+(`). Fixable by mod-morphing the combo bindings too, at the cost of more machinery.

### 4. The leader has no timeout

An accidental namespace combo stays armed until a key completes or fails to match a sequence. Worth a timeout, or a visible indicator on the display.

## Tests

`tests/test_hrm_mods.py` — 17 cases, all passing on hardware: two-mod chords on both hands (all four combo-overlapping pairs), three-mod chords, repeated hold/release cycles at 80/150/300 ms cadences, the tap path of every rewired combo (including the German leader sequence `E A` → ä), the same-hand veto swept across 130–275 ms gaps, and the press-order rules in both directions.
