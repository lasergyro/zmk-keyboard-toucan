# How a keypress resolves

This document derives the behaviour of the Toucan keymap from the firmware
mechanisms it is built out of. It proceeds bottom-up: the event objects, the
pipeline that dispatches them, each behaviour in isolation, then the
compositions this keymap builds from them. The user-facing rules in §9 and the
boundary cases in §10 are consequences of §§2–8, not independent facts.

Sources of truth: [config/toucan.keymap](../config/toucan.keymap),
[config/combos.dtsi](../config/combos.dtsi), [config/leader.dtsi](../config/leader.dtsi).
Mechanism references are to the vendored firmware under [external/zmk/](../external/zmk/).
Every timing constant is quoted from those files; the measured outcomes in §10
come from [tests/test_hrm_mods.py](../tests/test_hrm_mods.py), which drives the
hardware over RPC and reads back HID reports.

---

## 1. Objects

Each object is defined only in terms of the ones above it.

**Key position** — an integer naming one switch, `0`–`41`. Positions are
physical and carry no meaning on their own.

**Position event** (`zmk_position_state_changed`) — `(position, pressed|released,
timestamp)`. The matrix scanner raises one per switch transition. This is the
only input to everything below.

**Behaviour, binding, invoke** — a behaviour is a device exposing a press handler
and a release handler. A *binding* is a behaviour together with up to two
integer parameters, written `&kp LCTRL`. To *invoke* a binding is to call one of
its behaviour's two handlers with those parameters and the originating position.
A handler may invoke further bindings.

**Layer** — a total map from key position to binding. Layers are numbered
(`BASE 0`, `NAV 1`, `FN 2`, `PAD 3`, `PAN 4`) and any number may be active at
once. To resolve a position, the keymap scans active layers from the highest
number down and invokes the first binding that is not `&trans`; `&trans` means
"defer to the layer below". Separately, several mechanisms below consult
`zmk_keymap_highest_layer_active()` — the highest active layer *number*,
irrespective of what that layer binds.

**Usage page, usage ID** — HID identifies an input control by a *usage page*
(which vocabulary of controls) and a *usage ID* (which control within it). Page
`0x07`, Keyboard/Keypad, holds letters and modifiers; page `0x0C`, Consumer,
holds volume and brightness. Keyboard-page usages name **physical keys, not
characters**: usage `0x26` is "Keyboard 9 and `(`", and the host's layout decides
which of the two it produces.

**Keycode** — ZMK packs a usage page, a usage ID, and an 8-bit *implicit
modifier* field into one 32-bit value
([hid_usage_pages.h:13](../external/zmk/app/include/dt-bindings/zmk/hid_usage_pages.h#L13),
[modifiers.h:19](../external/zmk/app/include/dt-bindings/zmk/modifiers.h#L19)).
Because there is no standalone `(` usage to send, `LPAR` is *defined* as
`LS(N9)` — usage `0x26` with `MOD_LSFT` set in its implicit-modifier field
([keys.h:188](../external/zmk/app/include/dt-bindings/zmk/keys.h#L188)). That
is what "shifted keycode" means here: one keycode that carries its own shift.

**Implicit vs. explicit modifiers** — implicit modifiers ride along inside a
keycode and are asserted for exactly as long as that key is held. *Explicit*
modifiers come from pressing a modifier in its own right (`&kp LCTRL`) and
persist until it is released. The two are tracked in separate registers
([hid.c:42-43](../external/zmk/app/src/hid.c#L42)).

**Keycode event** (`zmk_keycode_state_changed`) — `(usage page, usage ID,
implicit mods, pressed|released)`. `&kp` raises one per press and per release.

**HID report** — a modifier byte plus six usage-ID slots, sent to the host. The
modifier byte is `(explicit & ~masked) | implicit`
([hid.c:48](../external/zmk/app/src/hid.c#L48)). The `masked` register is set
only by mod-morphs (§6).

## 2. The pipeline

Both event types are broadcast to *subscribers* in a fixed order. A subscriber
is a callback registered against an event type; each one returns one of three
verdicts, which determine whether the event continues down the chain:

| Verdict | Effect |
|---|---|
| **bubble** | pass the event to the next subscriber |
| **handled** | stop; the event is discarded |
| **captured** | stop; the subscriber has stored the event and may re-raise it later |

The order is link order — `.event_subscription` is emitted without sorting
([zmk-events.ld](../external/zmk/app/include/linker/zmk-events.ld)), so it follows
the source list in [app/CMakeLists.txt](../external/zmk/app/CMakeLists.txt).
The three subscribers to position events sit at lines 51, 69 and 76:

```
position event
    │
    ├─► hold-tap   (behavior_hold_tap.c:727)
    ├─► combo      (combo.c:489)
    └─► keymap     resolves the position to a binding and invokes it
                          │
                          ▼
                      keycode event
                          │
                          ├─► hold-tap   captures modifier keycodes while undecided
                          ├─► combo      timestamps non-modifier presses (idle tracking)
                          ├─► leader     consumes keycodes while armed (§8)
                          └─► HID        report sent to the host
```

What each subscriber captures, and for how long:

| Subscriber | Captures | While |
|---|---|---|
| hold-tap | *every* position event, and modifier keycode events | one hold-tap is undecided (§4) |
| combo | position events belonging to a candidate combo | the candidate set is non-empty and un-expired (§3) |
| keymap | nothing — it invokes a binding and returns | — |

Two consequences, used by number throughout:

**(2a)** The keymap is the last subscriber to position events, so a position
event captured upstream never reaches it and the binding on that position is
never invoked. Concretely: while a combo is a candidate, the hold-taps bound to
its positions are not merely overridden, they are never constructed.

**(2b)** Capture defers an event; it does not discard one — that is the
difference between **captured** and **handled**. When a hold-tap resolves it
re-raises the position events it captured via
[`ZMK_EVENT_RAISE_AT(…, behavior_hold_tap)`](../external/zmk/app/src/behaviors/behavior_hold_tap.c#L237),
which re-enters the chain *at* the hold-tap subscriber and continues on through
combo and keymap. The re-raised events carry their original timestamps, so a
combo whose positions were deferred by an undecided hold-tap is still measured
against its timeout from the original press — and can still fire.

## 3. Combos

A combo is a set of key positions, a binding, a `timeout-ms`, a layer mask, and
a `require-prior-idle-ms`. When it fires, its binding is invoked in place of the
bindings its positions would otherwise have resolved to.

On the first position press, candidates are those combos containing that
position whose layer mask includes the **highest active layer** and whose
prior-idle window has elapsed since the last non-modifier keycode
([combo.c:162](../external/zmk/app/src/combo.c#L162)). Each further press
intersects the candidate set. A combo fires when all of its positions are held
and the candidate set has narrowed to it; candidates expire `timeout-ms` after
the *first* press, at which point the captured positions are re-raised and
resolve normally.

The keymap defines two families:

| Family | Positions | Timeout | Prior idle | Contents |
|---|---|---|---|---|
| horizontal | adjacent keys within a row | 72 ms | 150 ms | `ESC`, `TAB`, cut/copy/paste, `BSPC`, `DEL`, brackets, parens, leader namespaces |
| vertical | adjacent keys within a column | 120 ms | 50 ms | the symbol layer: `@ # $ % ` \ = ~ ^ + * & _ - / \|` |

The prior-idle windows are what keep the homerow usable: a horizontal combo
cannot fire within 150 ms of your last keystroke, so rolling `s`→`d` at typing
speed produces `sd`, not `ALT+SHIFT+TAB`.

Layer gating: symbol and editing combos are defined on `BASE NAV`; parens,
brackets and the three namespace combos are `BASE`-only, and NAV rebinds the
same positions to `< >` and `{ }`.

## 4. Hold-tap

A hold-tap is a behaviour naming two further bindings, of which it invokes
exactly one. On press it enters the *undecided* state and starts a
`tapping-term-ms` timer. At most one hold-tap is undecided at a time: while one
is, it captures every subsequent position event and every modifier keycode
event, so nothing downstream — combo or keymap — resolves before it does, and no
second hold-tap can be constructed. Its decision releases the captured events
back into the chain (§2b).

**Decision moments.** Under the `balanced` flavour used here
([behavior_hold_tap.c:283](../external/zmk/app/src/behaviors/behavior_hold_tap.c#L283)):

| Moment | Resolution |
|---|---|
| its own key released | tap |
| another key **released** while undecided | hold |
| tapping term expires | hold |
| forced-tap gate (below) | tap |

Note that another key going *down* decides nothing; the pair must complete.

**Forced-tap gates**, checked on press
([`is_quick_tap`](../external/zmk/app/src/behaviors/behavior_hold_tap.c#L144)):

1. `require-prior-idle-ms` — any key tapped within the window immediately before
   this press forces the tap.
2. `quick-tap-ms` — the *same* position tapped within the window forces the tap.

Here these are 200 ms and 175 ms. Because gate 1 is checked first and its window
is the wider of the two, gate 2 never adds a case: any same-position re-press
inside 175 ms is already inside 200 ms. Repeat-letter typing (`ll`) is covered
by gate 1.

**Positional veto.** `hold-trigger-key-positions` lists the positions that are
permitted to produce a hold. The behaviour records the first *other* position
pressed after it, and after the flavour has chosen, `decide_positional_hold`
downgrades hold → tap if that position is not in the list
([behavior_hold_tap.c:506](../external/zmk/app/src/behaviors/behavior_hold_tap.c#L506)).
`hold-trigger-on-release` is deliberately left off, so the recorded position is
the one *pressed*, not released.

**(4a)** The veto is a filter on a decision, not a revocation of one. If no other
key is pressed before the tapping term expires, `position_of_first_other_key_pressed`
is still unset and the veto returns early — the hold stands permanently. This
is the whole content of the first boundary case in §10.

## 5. Homerow mods

Two hold-tap templates, differing only in their trigger sets:

```
hml:  hold = &kp <mod>,  tap = &kp <letter>,  triggers = KEYS_R THUMBS MODS_LH
hmr:  hold = &kp <mod>,  tap = &kp <letter>,  triggers = KEYS_L THUMBS MODS_RH
```

with `tapping-term-ms = 280`, `require-prior-idle-ms = 200`, `quick-tap-ms = 175`,
`flavor = balanced` for both.

`MODS_LH` / `MODS_RH` are that hand's own four homerow positions. So a left HRM
permits a hold when the next key is on the right hand, on a thumb, or is another
left homerow mod — and vetoes it for every other left-hand key. Applying §4:

| First other key pressed | Resolution |
|---|---|
| opposite hand, or a thumb | modifier |
| same hand, another homerow mod | modifier (chords) |
| same hand, anything else | letter (veto) |
| none, term expires | modifier |

Assignment (`BASE`): `A S D F` → `LCTRL LALT LGUI LSHFT`, `J K L ?` →
`RSHFT RGUI RALT RCTRL`. Each hand carries all four modifiers.
`NAV` keeps left-hand HRMs only (`CTRL`/`ALT`/`GUI` on `A S D`, `SHIFT` falling
through to the bottom-row pinky) and binds the arrows as plain `&kp` so a long
press repeats. `FN` reinstates HRMs on both hands over `F4–F6` and `4 5 6 0`.

## 6. Order sensitivity

Row 4 of the table above is a problem: a bare held HRM resolves to its modifier
once the term expires, so `CTRL+ALT` held followed by a held `J` would add
`RSHIFT` instead of typing `j`. `hold-trigger-key-positions` cannot express
"only ever hold positionally".

Each HRM is therefore wrapped in a mod-morph keyed on the **opposite hand's**
modifiers:

```
HRM_L(name, MOD, TAP):  mods = MODS_RIGHT;  keep-mods = MODS_RIGHT
                        normal = &hml MOD TAP        morph = &kp TAP
HRM_R(name, MOD, TAP):  mods = MODS_LEFT;   keep-mods = MODS_LEFT
```

A mod-morph tests `zmk_hid_get_explicit_mods()` at press time
([behavior_mod_morph.c:48](../external/zmk/app/src/behaviors/behavior_mod_morph.c#L48))
and invokes the morph binding if any listed modifier is held. `keep-mods` sets
`masked_mods = mods & ~keep_mods = 0`, so the triggering modifiers stay in the
HID report instead of being stripped for the duration of the press.

Left HRMs emit `L*` modifiers and right HRMs emit `R*`; that asymmetry is what
makes the two hands distinguishable to the morph. Consequences:

**(6a)** While either hand holds modifiers, the other hand's homerow keys are
plain `&kp` — they type and repeat, and cannot become modifiers.

**(6b)** A hand's own modifiers never trigger its own morph, so same-hand chords
are unaffected: `A`+`S` is still `CTRL+ALT`, and a third (`A`+`S`+`D`) still
adds `GUI`.

**(6c)** Cross-hand modifier chords are unreachable by construction. This is the
price of (6a), and it is affordable only because each hand carries all four
modifiers.

**(6d)** The outer bottom-row `LSHFT`/`RSHFT` keys are ordinary `&kp` and emit
explicit `L`/`R` modifiers, so they trigger the same morph — holding the left
pinky shift makes the whole right homerow type letters.

## 7. Chorded combos

Four adjacent homerow-mod pairs are also combo positions. By (2a) their
hold-taps are never constructed, so a *held* pair emitted a repeating combo
keycode instead of two modifiers.

The fix composes all three mechanisms. Each such combo is bound not to its
symbol but to a hold-tap whose tap binding is the symbol and whose hold binding
is a macro that presses both modifiers:

```
combo (positions) ──► chrm_* (hold-tap, same 280/200/175 config and trigger set)
                        ├─ tap  ──► the symbol / namespace macro
                        └─ hold ──► macro: press both mods · pause for release · release both
```

The macro uses explicit `&kp` presses so the modifiers survive other keys being
pressed and released while the chord is down; implicit mods would not.

| Pair | Positions | Tap | Hold |
|---|---|---|---|
| `S`+`D` | `LM3 LM2` | `LS(LA(TAB))` — window switch | `LALT`+`LGUI` |
| `D`+`F` | `LM2 LM1` | German leader namespace | `LGUI`+`LSHFT` |
| `J`+`K` | `RM1 RM2` | `(` (`<` on NAV, `<` under shift) | `RSHFT`+`RGUI` |
| `K`+`L` | `RM2 RM3` | `)` (`>` on NAV, `>` under shift) | `RGUI`+`RALT` |

The remaining pair `A`+`S` carries no combo, so it chords through §5 directly.

## 8. Leader

`&leader` subscribes to *keycode* events, downstream of the keymap
([behavior_leader_key.c:204](../.zmk-workspace/modules/zmk/leader-key/src/behaviors/behavior_leader_key.c#L204)).
Three combos arm it via a macro that invokes `&leader` and then taps a namespace
letter, so the namespace is the first element of every sequence:

| Combo | Positions | Namespace | Sequences |
|---|---|---|---|
| `H`+`J` | `RM0 RM1` | `L` | Greek letters |
| `D`+`F` | `LM2 LM1` | `E` | `E A` `E O` `E U` `E S` → ä ö ü ß |
| `V`+`B` | `LB1 LB0` | `N` | bluetooth profiles, output mode, host mode, bootloader, reset |

While armed, each keycode press is classified:

| Keycode | Action |
|---|---|
| in `ignore-keys` (`LSHFT`, `RSHFT`) | bubbles; sequence position unchanged |
| extends a candidate sequence | consumed (**handled**); host sees nothing |
| completes a sequence | consumed; the sequence's binding is invoked |
| matches no candidate | leader disarms and the keycode **bubbles** to the host |

There is no timeout. An armed leader persists until a keycode completes or
fails a sequence, and the failing keycode is the one that both disarms it and
reaches the host.

## 9. Rules that follow

1. **Modifiers first, then keys.** Press order alone decides what is a modifier.
   Homerow keys pressed before anything else become modifiers when held; homerow
   keys pressed while modifiers are already down type normally however long you
   hold them. Hold `A`+`S`, then hold `J` → `CTRL+ALT+j`, repeating. *(6a)*
2. **Modifier chords are single-handed.** Any combination is reachable on either
   hand; none is reachable across hands. *(6b, 6c)*
3. **280 ms separates letter from modifier**, with two forced-letter shortcuts:
   any keystroke in the preceding 200 ms, and re-pressing the same key inside
   175 ms. *(§4)*
4. **A hand holding modifiers modifies only the other hand.** Pressing a
   non-homerow key on the same hand as an undecided HRM forces the letter, so
   hold `D`, press `C` gives `dc`. Use the other hand's `GUI` (`K`) for `Cmd+C` —
   or the dedicated combos: `X`+`V` cut, `X`+`C` copy, `C`+`V` paste. *(§5)*
5. **Adjacent homerow pairs are both a chord and a combo**, disambiguated by
   duration. *(§7)*
6. **A stray namespace combo consumes exactly one following keystroke.** *(§8)*

## 10. Boundary cases

Real, measured, and each one a direct consequence of the mechanism named.

**A lone modifier held past the term modifies its own hand.** By (4a) the
positional veto cannot downgrade a hold that has already resolved. Holding `D`
alone for more than 280 ms produces `GUI`, and a same-hand `C` pressed after
that is `Cmd+C`. Sweeping the gap between `D` and `C`:

| Gap | Result | Why |
|---|---|---|
| < 120 ms | `\` | the vertical `D`/`C` combo is still a candidate (§3) |
| 130–275 ms | `dc` | `D`'s hold-tap is undecided; `C` triggers the veto (§5) |
| > 280 ms | `Cmd+C` | `D` already resolved to `GUI` (4a) |

Reaching this requires deliberately holding the modifier alone first; no
typing-speed sequence gets there. The same shape holds for every homerow column:
`S`+`X` → `` ` ``, `F`+`V` → `=`, `G`+`B` → `~`.

**A combo under held modifiers is still a combo.** Rule 1 is a property of the
mod-morph, which is a binding in the keymap; by (2a) the combo captures those
positions before the keymap resolves them, so the morph is never invoked.
Holding `CTRL+ALT` and then holding `J`+`K` gives
`CTRL+ALT+SHIFT+GUI`, not `ctrl+alt+jk`. Tapping `J`+`K` under held modifiers
gives `CTRL+ALT+(`, which is the case that actually matters.

**Four outcomes per homerow key.** Letter, modifier, member of a horizontal
combo, member of a vertical combo — selected by timing alone. This is inherent
to placing combos on the homerow; alternatives are laid out in
[plans/2026-07-13-homerow-mods-vs-combos.md](../plans/2026-07-13-homerow-mods-vs-combos.md).

## 11. Constants

| Constant | Value | Defined in |
|---|---|---|
| HRM `tapping-term-ms` | 280 ms | `toucan.keymap` |
| HRM `require-prior-idle-ms` | 200 ms | `toucan.keymap` |
| HRM `quick-tap-ms` | 175 ms (subsumed, §4) | `toucan.keymap` |
| Combo `timeout-ms`, horizontal | 72 ms (`18 * 4`) | `combos.dtsi` |
| Combo `timeout-ms`, vertical | 120 ms (`30 * 4`) | `combos.dtsi` |
| Combo `require-prior-idle-ms`, horizontal | 150 ms | `combos.dtsi` |
| Combo `require-prior-idle-ms`, vertical | 50 ms | `combos.dtsi` |
| Leader sequence timeout | none | `behavior_leader_key.c` |
