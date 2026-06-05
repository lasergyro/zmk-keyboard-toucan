---
name: generic-patcher
description: A tool to apply simple text search-and-replace patches to files in the repository.
---

# Generic Patcher

This skill provides a way to make targeted edits to files without needing to write custom Python scripts or use complex `sed` commands that might fail across different operating systems.

## Usage

Use the script located at `scripts/patcher.py`.

```bash
uv run scripts/patcher.py <file> --search "<search_text>" --replace "<replace_text>"
```

### Parameters
- `<file>`: The relative or absolute path to the file you want to modify.
- `--search`: The exact text you want to find and replace. This must be an exact substring match.
- `--replace`: The text you want to insert in place of the search text.

### When to use
- Use this when the native `replace_file_content` or `multi_replace_file_content` tools are failing or when you need to make identical search/replace edits across multiple files in a shell loop.
- Use this to avoid cluttering the repository with one-off Python scripts for modifying files.

### Note
- If the search text is not found, the script will exit with an error.
- Be careful with matching generic strings; the patcher will replace all occurrences of the search text in the file.
