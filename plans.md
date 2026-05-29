# Development Plans & Guidelines

## Roadmap

### Completed
- Round 1: Touchpad gesture implementation — state machine, smart drag, force drag, persistent params, live tuning.
- Round 2: Leader key — German umlauts, Greek characters, SYS namespace (BT, output modes, studio, reset, boot). Modules: `zmk-leader-key`, `zmk-unicode`.
- Round 3: Combos, HRMs, layer restructure — layers (BASE/NAV/FN/PAD/PAN), timeless homerow mods, two-key symbol/nav combos, namespace combo mechanism, schematic drawer refactor.

### Deferred
- Gaming layer, Swapper/Alt-Tab, extended Unicode sets
- Testing infrastructure (`qi`/`qo` synthetic tests, `rstart`/`rend` real-world traces) — see `rpc.md`
