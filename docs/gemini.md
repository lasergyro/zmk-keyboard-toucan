# Gemini agent tool conventions

Tool-usage rules specific to the Gemini agent harness (`grep_search`, `list_dir`, `run_command`, `manage_task`). They do not apply to other agents or to running commands by hand. To prevent repetitive mistakes during future sessions, follow these rules when using tools:

- **Avoid `cat | grep` or `grep` in bash**: Always prioritize the `grep_search` tool over running `grep` in a bash command. Do not use `cat` for viewing files or `grep` for searching files via the `run_command` tool.
- **File Finding**: Do not use `find . -name "..."` as an unbounded bash command (it runs as a long background task). Instead, use `grep_search` with the `Includes` filter or `list_dir` to find files efficiently.
- **Task Logs**: Never use `cat` to read a background task's log file (e.g., `.system_generated/tasks/task-xxx.log`) manually, as it may not exist yet or might be truncated.
- **Background Tasks**: Do not poll a running background task repeatedly using `manage_task status`. Launch the task and yield your turn by making no more tool calls; the system will automatically notify you and wake you up when the task completes.
