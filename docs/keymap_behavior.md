# How a keypress is resolved

Four mechanisms can each claim the same physical keypress: **layers**, **combos**, **homerow mods** (hold-taps), and the **leader**. This document says who wins, and when. It describes the keymap as built, and every timing figure below was measured on hardware (`tests/test_hrm_mods.py`).

## The order of claims

A keypress travels down this chain. The first mechanism that claims it stops the ones below from seeing it.

1. **An unresolved homerow mod defers everything.** If a homerow key is already down and the firmware has not yet decided whether it is a modifier or a letter, every later keypress is *parked* until that decision is made — combos included. This is why holding CTRL and then hitting a combo still gives you CTRL + the combo.

2. **Combos claim raw key positions.** Two keys pressed inside the combo window are a combo, and neither the keymap nor the homerow mods ever see them. Combos are layer-gated: only combos defined for the active layer can fire.

3. **The keymap runs the binding.** For a homerow key this means: check whether the *opposite* hand is already holding modifiers (if so, type the letter), otherwise start the hold-vs-tap decision.

4. **The leader consumes keycodes.** Once a namespace combo has armed the leader, the keys that follow feed the sequence instead of reaching the host.

## The rules, in words

**Modifiers first, then keys.** The order you press decides what is a modifier and what is not. Homerow keys pressed *before* anything else become modifiers when held; homerow keys pressed *after* modifiers are already down type normally, even if you hold them. Hold `A`+`S`, then hold `J` → `CTRL+ALT+j`, repeating, not `CTRL+ALT+SHIFT`.

**Modifier chords live on one hand.** Two or more homerow mods on the *same* hand chord together (`A`+`S` → CTRL+ALT). Each hand carries all four modifiers, so any combination is reachable without crossing hands. The flip side of the order rule is that you can no longer build a chord across hands — the second hand types letters.

**Hold past 280 ms for a modifier; release sooner for a letter.** A homerow key you release inside 280 ms is its letter. There are two shortcuts that force the letter even if you hold longer: typing in the last 200 ms (so fast typing never produces stray modifiers), and re-pressing a key you just tapped within 175 ms (so `ll` works).

**Adjacent homerow pairs are both a chord and a combo.** `S+D`, `D+F`, `J+K` and `K+L` are combos *and* two-modifier chords. Tapping the pair gives the combo; holding it gives both modifiers:

| Pair | Tap | Hold |
|------|-----|------|
| `S`+`D` | `ALT+SHIFT+TAB` (window switch) | ALT + GUI held |
| `D`+`F` | German leader namespace | GUI + SHIFT held |
| `J`+`K` | `(` | SHIFT + GUI held |
| `K`+`L` | `)` | GUI + ALT held |

**A hand that holds modifiers only modifies the other hand.** Modifiers are for the opposite hand's keys. Pressing a non-modifier key on the *same* hand as an unresolved homerow mod cancels the modifier and types both keys as letters — hold `D`, press `C`, and you get `dc`, not `Cmd+C`. Use the other hand's GUI (`K`) to send `Cmd+C`. The one exception is documented under Rough edges.

**A stray leader eats your next keystroke.** The leader has no timeout. If you trip a namespace combo by accident, it stays armed until a key completes a sequence or fails to match one — the failing key is what disarms it, and it passes through.

## Timings

| What | Window |
|------|--------|
| Homerow mod: hold to get the modifier | 280 ms |
| Homerow mod: suppressed after recent typing | 200 ms |
| Homerow mod: re-tap repeats the letter | 175 ms |
| Combo: horizontal / namespace pairs | 72 ms |
| Combo: vertical pairs (symbols) | 120 ms |
| Leader: time to complete a sequence | no limit |

## Rough edges

These are real, measured, and worth knowing about.

**A lone modifier held past 280 ms still modifies its own hand.** The positional veto runs when the next key is *pressed*, so it can only cancel a modifier that has not been decided yet. If you hold `D` on its own for longer than the tapping term, it has already become GUI, and nothing can take that back — a `C` pressed afterwards is `Cmd+C`. Measured:

| Gap between `D` and `C` | Result |
|-------------------------|--------|
| under ~120 ms | `\` — the vertical `D`/`C` symbol combo fires |
| 130–275 ms | `dc` — both keys type as letters ✓ |
| over 280 ms | `Cmd+C` — the modifier had already resolved |

This is the one path left to a same-hand modifier + key, and it requires deliberately holding the modifier alone first; no typing-speed sequence reaches it. The same shape applies to `S`+`X` (→ `` ` ``), `F`+`V` (→ `=`) and the other homerow columns. Note the keymap sidesteps the common cases anyway by putting cut/copy/paste on their own combos (`X`+`C`, `X`+`V`, `C`+`V`).

**A combo under held modifiers is still a combo.** Holding `CTRL+ALT` and then holding `J`+`K` gives `CTRL+ALT+SHIFT+GUI` (the pair's modifiers), not `ctrl+alt+jk`. The order rule does not reach inside combos, because combos claim key positions before the keymap. Tapping `J`+`K` under held modifiers gives `CTRL+ALT+(`, which is the case that actually matters.

**Two mechanisms answer for one key.** Every homerow key now has four possible outcomes (letter, modifier, part of a horizontal combo, part of a vertical combo), selected by timing alone. That is inherent to putting combos on the homerow; the alternatives are in [plans/2026-07-13-homerow-mods-vs-combos.md](../plans/2026-07-13-homerow-mods-vs-combos.md).
