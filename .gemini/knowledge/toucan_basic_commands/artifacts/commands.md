# Toucan Keyboard - Basic Commands and Workflow
Refer to the project `README.md` for extended guidelines.

**Dev logs**: for each specific issue keep a log/notes in a document in `plans/[date]-[topic].md`; keep it up to date as you resolve the issue.

**Generic Patcher**: if normal edit tools are not the first choice, use the generic patching tool `scripts/patcher.py` to make targeted changes to files without needing to write custom Python scripts each time. You can invoke it like `python3 scripts/patcher.py <file> --search "<search_text>" --replace "<replace_text>"`.

To prevent repetitive mistakes during future sessions, follow these rules when using tools:
- **Avoid `cat | grep` or `grep` in bash**: Always prioritize the `grep_search` tool over running `grep` in a bash command. Do not use `cat` for viewing files or `grep` for searching files via the `run_command` tool.
- **File Finding**: Do not use `find . -name "..."` as an unbounded bash command (it runs as a long background task). Instead, use `grep_search` with the `Includes` filter or `list_dir` to find files efficiently.
- **Task Logs**: Never use `cat` to read a background task's log file (e.g., `.system_generated/tasks/task-xxx.log`) manually, as it may not exist yet or might be truncated.
- **Background Tasks**: Do not poll a running background task repeatedly using `manage_task status`. Launch the task and yield your turn by making no more tool calls; the system will automatically notify you and wake you up when the task completes.

## Scripts
* `./debug.sh` for various CLI interactions
* `./build.sh` for compiling

## Testing while investigating
Instead of running ad-hoc commands in the shell, write new test scripts in `./tests` and run them with `uv`:
```bash
uv run tests/my_test_script.py
```
This ensures reproducible scenarios and captures the exact output from the board.

### Basic Project Commands
- **Build Firmware:**
  `./debug.sh build`
- **Flash Firmware:**
  `./debug.sh upload` 
- **Execute Python:**
  All python scripts must be run via `uv run`.
- **Execute Python Tests:**
  e.g. `uv run tests/test_pad.py`
- **Investigating Bugs:**
  Instead of doing ad-hoc investigations in the shell, write them as a new test script in `./tests` and run them with `uv run`.
- **Stream Live Device Logs:**
  `./debug.sh logs both`

### Hardware & Architecture Facts
- The touchpad parser (`cirque_pinnacle_inject_abs`) runs exclusively on the **Right Half**.
- Python automation scripts communicate exclusively with the **Left Half** over USB.
- Events injected via `qi` are sent from Left to Right over BLE.

