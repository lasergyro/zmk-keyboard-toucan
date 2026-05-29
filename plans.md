# Development Plans & Guidelines

## Roadmap

### Completed
- Round 1: Touchpad gesture implementation — state machine, smart drag, force drag, persistent params, live tuning.
- Round 2: Leader key — German umlauts, Greek characters, SYS namespace (BT, output modes, studio, reset, boot). Modules: `zmk-leader-key`, `zmk-unicode`.
- Round 3: Combos, HRMs, layer restructure — layers (BASE/NAV/FN/PAD/PAN), timeless homerow mods, two-key symbol/nav combos, namespace combo mechanism, schematic drawer refactor.

### Deferred
- Gaming layer, Swapper/Alt-Tab, extended Unicode sets
- Testing infrastructure (`qi`/`qo` synthetic tests, `rstart`/`rend` real-world traces) — see `rpc.md`

---

## Testing Standards

All automated tests must adhere to the following architecture:
- **Peripheral Injection for Touch**: The split transport batches the BLE/RPC messages, causing them to arrive at the peripheral almost simultaneously. This means that timing/waits should be done on the left half, with some flushing of messages.
- **Queued Execution**: No `time.sleep()` in test scripts. All timing and event sequences must be queued via `qi` and executed via `qo`.
- **Global Position Injection**: Peripheral key events must be injected at the Central half using their global position indices.
- **Clean Abstraction**: Tests must not import `serial_rpc.py` directly. All communication must use the `debug_tool.RPCSession` abstraction.
- **Isolate Environment**: Use `quarantine on` during tests to block physical interference.
- **Timestamp Drift**: Be aware that the `left_log` and `right_log` Zephyr uptime timestamps can drift or start with several seconds of offset.

---

## Agent Command Guidelines

**Knowledge Item Reference**: The core commands and workflow constraints for this project have been extracted to a Knowledge Item at [commands.md](file:///Users/ma/.gemini/antigravity-ide/knowledge/toucan_basic_commands/artifacts/commands.md). Ensure you review it if context is lost.

To prevent repetitive mistakes during future sessions, follow these rules when using tools:
- **Avoid `cat | grep` or `grep` in bash**: Always prioritize the `grep_search` tool over running `grep` in a bash command. Do not use `cat` for viewing files or `grep` for searching files via the `run_command` tool.
- **File Finding**: Do not use `find . -name "..."` as an unbounded bash command (it runs as a long background task). Instead, use `grep_search` with the `Includes` filter or `list_dir` to find files efficiently.
- **Task Logs**: Never use `cat` to read a background task's log file (e.g., `.system_generated/tasks/task-xxx.log`) manually, as it may not exist yet or might be truncated.
- **Background Tasks**: Do not poll a running background task repeatedly using `manage_task status`. Launch the task and yield your turn by making no more tool calls; the system will automatically notify you and wake you up when the task completes.
