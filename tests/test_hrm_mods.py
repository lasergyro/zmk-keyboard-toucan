#!/usr/bin/env python3
"""Same-hand homerow-mod chords (two or more modifiers on one hand).

Injects key-position events with human-like timing via qi/qo and inspects the
captured HID keyboard reports.

Key positions (42-key):  A=13 S=14 D=15 F=16   J=19 K=20 L=21
Left HRMs:  A=LCTRL S=LALT D=LGUI F=LSHFT
Right HRMs: J=RSHFT K=RGUI L=RALT
"""

import pytest

# HID modifier usages, as emitted by the RPC HID capture (0xE0 + bit index).
LCTRL, LSHFT, LALT, LGUI = 0xE0, 0xE1, 0xE2, 0xE3
RCTRL, RSHFT, RALT, RGUI = 0xE4, 0xE5, 0xE6, 0xE7

MOD_NAMES = {
    LCTRL: "LCTRL", LSHFT: "LSHFT", LALT: "LALT", LGUI: "LGUI",
    RCTRL: "RCTRL", RSHFT: "RSHFT", RALT: "RALT", RGUI: "RGUI",
}

A, S, D, F = 13, 14, 15, 16
J, K, L = 19, 20, 21

# Human-like timing for a deliberate two-key mod chord.
ROLL_MS = 45       # offset between the two keys of the chord going down
HOLD_MS = 600      # how long the chord is held (well past the 280ms tapping term)
RELEASE_MS = 50    # offset between the two keys coming back up
GAP_MS = 250       # idle between repeats of the chord
LEAD_MS = 400      # idle before the first press (clears require-prior-idle-ms)


def chord(pos_a, pos_b, lead_ms=LEAD_MS, hold_ms=HOLD_MS):
    """One human-paced press-hold-release of a two-key chord."""
    return [
        f"P,{lead_ms},{pos_a},1",
        f"P,{ROLL_MS},{pos_b},1",
        f"P,{hold_ms},{pos_a},0",
        f"P,{RELEASE_MS},{pos_b},0",
    ]


def parse_keys(trace):
    """['K,12,229,1', ...] -> [(code, value), ...] keyboard events only."""
    events = []
    for line in trace:
        parts = line.split(",")
        if len(parts) == 4 and parts[0] == "K":
            events.append((int(parts[2]), int(parts[3])))
    return events


def describe(events):
    return [
        f"{MOD_NAMES.get(code, hex(code))}{'v' if val else '^'}" for code, val in events
    ]


def mod_pairs(events, *mods):
    """Down/up cycles seen for the given mods, e.g. [(down, down), (up, up)] count."""
    wanted = set(mods)
    return [(c, v) for c, v in events if c in wanted]


def non_mod_keys(events):
    return [(c, v) for c, v in events if c < 0xE0]


@pytest.mark.parametrize(
    "name,pos_a,pos_b,mod_a,mod_b",
    [
        ("right_shift_gui", J, K, RSHFT, RGUI),   # overlaps the `lpar` combo
        ("right_gui_alt", K, L, RGUI, RALT),      # overlaps the `rpar` combo
        ("left_alt_gui", S, D, LALT, LGUI),       # overlaps the `tab` combo
        ("left_gui_shift", D, F, LGUI, LSHFT),    # overlaps the `german_ns` combo
    ],
)
def test_same_hand_mod_chord_holds_mods(rpc_left, name, pos_a, pos_b, mod_a, mod_b):
    """Holding two same-hand HRMs must hold both mods, not fire the combo."""
    trace = rpc_left.run_scenario(chord(pos_a, pos_b))
    events = parse_keys(trace)

    assert not non_mod_keys(events), (
        f"{name}: chord emitted non-modifier keycodes (a combo fired): "
        f"{non_mod_keys(events)} / full trace {describe(events)}"
    )
    assert mod_pairs(events, mod_a, mod_b) == [
        (mod_a, 1), (mod_b, 1), (mod_a, 0), (mod_b, 0),
    ], (
        f"{name}: expected {MOD_NAMES[mod_a]}+{MOD_NAMES[mod_b]} held then released, "
        f"got {describe(events)}"
    )


def test_three_mod_chord(rpc_left):
    """A+S+D must hold CTRL+ALT+GUI (S+D alone is the `tab` combo)."""
    trace = rpc_left.run_scenario([
        f"P,{LEAD_MS},{A},1", f"P,{ROLL_MS},{S},1", f"P,{ROLL_MS},{D},1",
        f"P,{HOLD_MS},{A},0", f"P,{ROLL_MS},{S},0", f"P,{ROLL_MS},{D},0",
    ])
    events = parse_keys(trace)
    assert not non_mod_keys(events), f"three-mod chord fired a combo: {describe(events)}"
    assert {c for c, v in events if v} == {LCTRL, LALT, LGUI}, describe(events)


@pytest.mark.parametrize(
    "name,pos_a,pos_b,mod_a,mod_b",
    [
        ("left_ctrl_alt", A, S, LCTRL, LALT),     # no combo on these positions
        ("right_shift_gui", J, K, RSHFT, RGUI),
    ],
)
def test_repeated_mod_chord_repeats_mods(rpc_left, name, pos_a, pos_b, mod_a, mod_b):
    """Press-hold-release of the same chord three times must hold the mods each time."""
    scenario = []
    for i in range(3):
        scenario += chord(pos_a, pos_b, lead_ms=LEAD_MS if i == 0 else GAP_MS)

    trace = rpc_left.run_scenario(scenario)
    events = parse_keys(trace)

    expected = [(mod_a, 1), (mod_b, 1), (mod_a, 0), (mod_b, 0)] * 3
    assert mod_pairs(events, mod_a, mod_b) == expected, (
        f"{name}: expected 3 down/up cycles of {MOD_NAMES[mod_a]}+{MOD_NAMES[mod_b]}, "
        f"got {describe(events)}"
    )
    assert not non_mod_keys(events), (
        f"{name}: chord emitted non-modifier keycodes: {non_mod_keys(events)}"
    )


# ── The combos themselves must still fire on a tap ───────────────────────────

TAP_MS = 60  # chord pressed and released well inside the 280ms tapping term

N9, TAB_KC, KP_A = 0x26, 0x2B, 0x04


def tap_chord(pos_a, pos_b):
    return [
        f"P,{LEAD_MS},{pos_a},1",
        f"P,20,{pos_b},1",
        f"P,{TAP_MS},{pos_a},0",
        f"P,20,{pos_b},0",
    ]


@pytest.mark.parametrize(
    "name,pos_a,pos_b,expect",
    [
        ("lpar", J, K, [(LSHFT, 1), (N9, 1), (LSHFT, 0), (N9, 0)]),          # (
        ("tab", S, D, [(LSHFT, 1), (LALT, 1), (TAB_KC, 1),                   # LS(LA(TAB))
                       (LSHFT, 0), (LALT, 0), (TAB_KC, 0)]),
    ],
)
def test_combo_still_fires_on_tap(rpc_left, name, pos_a, pos_b, expect):
    events = parse_keys(rpc_left.run_scenario(tap_chord(pos_a, pos_b)))
    assert sorted(events) == sorted(expect), f"{name}: got {describe(events)}"


def test_german_leader_combo_still_fires_on_tap(rpc_left):
    """Tapping D+F enters the German namespace; the `E A` sequence then types ä."""
    scenario = tap_chord(D, F) + [f"P,300,{A},1", f"P,{TAP_MS},{A},0"]
    events = parse_keys(rpc_left.run_scenario(scenario))
    # The unicode macro for ä emits a burst of keystrokes; a bare miss emits nothing
    # (leader swallows) or a plain `a`.
    assert len(events) > 2 and events != [(KP_A, 1), (KP_A, 0)], (
        f"German leader sequence did not run: {describe(events)}"
    )


# ── Press order decides which keys are modifiers ─────────────────────────────


def test_mods_then_opposite_hand_key_held(rpc_left):
    """Mods first, then an opposite-hand homerow key: the key types, even when held."""
    events = parse_keys(rpc_left.run_scenario([
        f"P,{LEAD_MS},{A},1", f"P,{ROLL_MS},{S},1",   # hold LCTRL+LALT
        f"P,300,{J},1", f"P,400,{J},0",               # then press and hold J
        f"P,60,{A},0", f"P,50,{S},0",
    ]))
    assert events == [
        (LCTRL, 1), (LALT, 1), (0x0D, 1), (0x0D, 0), (LCTRL, 0), (LALT, 0)
    ], f"expected CTRL+ALT+j, got {describe(events)}"


C_POS, X_POS = 27, 26   # LB2, LB3 — same hand as the left homerow mods
KP_C, KP_D, KP_X, KP_S = 0x06, 0x07, 0x1B, 0x16


@pytest.mark.parametrize("gap_ms", [130, 200, 250, 275])
def test_same_hand_key_never_makes_a_modifier(rpc_left, gap_ms):
    """Hold D (GUI), then press C on the same hand: must type `dc`, never Cmd+C.

    The gap is swept up to the 280ms tapping term: the positional veto has to fire
    on C's *press*, otherwise D's timer resolves to GUI first (the old Cmd+C bug).
    """
    events = parse_keys(rpc_left.run_scenario([
        f"P,{LEAD_MS},{D},1", f"P,{gap_ms},{C_POS},1",
        f"P,300,{C_POS},0", f"P,60,{D},0",
    ]))
    assert not any(c == LGUI for c, v in events), (
        f"gap={gap_ms}ms: same-hand key produced a modifier: {describe(events)}"
    )
    assert {c for c, v in events if v} == {KP_D, KP_C}, describe(events)


def test_same_hand_mod_chord_survives_the_veto(rpc_left):
    """The veto must not break same-hand *modifier* chords: A+S is still CTRL+ALT."""
    events = parse_keys(rpc_left.run_scenario(chord(A, S)))
    assert mod_pairs(events, LCTRL, LALT) == [
        (LCTRL, 1), (LALT, 1), (LCTRL, 0), (LALT, 0)
    ], describe(events)


def test_mods_first_then_same_hand_key_is_a_mod(rpc_left):
    """The opposite rule: same-hand homerow keys still chord as modifiers."""
    events = parse_keys(rpc_left.run_scenario([
        f"P,{LEAD_MS},{A},1", f"P,300,{F},1",          # LCTRL, then LSHFT (same hand)
        f"P,400,{F},0", f"P,60,{A},0",
    ]))
    assert events == [(LCTRL, 1), (LSHFT, 1), (LSHFT, 0), (LCTRL, 0)], describe(events)
