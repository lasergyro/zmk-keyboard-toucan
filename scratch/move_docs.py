import os
import re

files_to_move = [
    'TODOS.md',
    'human_interface.md',
    'rpc.md',
    'touchpad.md',
    'touchpad_acceleration.md',
    'touchpad_state_machine.md',
    'touchpad_state_machine.mmd'
]

os.makedirs('docs', exist_ok=True)

# 1. Update README.md
with open('README.md', 'r') as f:
    content = f.read()

for doc in files_to_move:
    # replace [Text](doc) with [Text](docs/doc)
    content = re.sub(r'\]\(' + re.escape(doc) + r'\)', '](docs/' + doc + ')', content)

with open('README.md', 'w') as f:
    f.write(content)

# 2. Update links INSIDE the files being moved
def update_internal_links(filepath):
    if not filepath.endswith('.md'):
        return
    with open(filepath, 'r') as f:
        content = f.read()
    
    def replacer(match):
        text = match.group(1)
        url = match.group(2)
        if url.startswith('http') or url.startswith('/') or url.startswith('#'):
            return f'[{text}]({url})'
        if url in files_to_move:
            return f'[{text}]({url})'
        # Also ignore mailto:, etc.
        if ':' in url and not url.startswith('http'):
            return f'[{text}]({url})'
        # Special check for links that already have ../
        if url.startswith('../'):
            return f'[{text}]({url})' # Although it should probably be updated too, but we didn't see any
        return f'[{text}](../{url})'

    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replacer, content)
    
    with open(filepath, 'w') as f:
        f.write(content)

for doc in files_to_move:
    if os.path.exists(doc):
        update_internal_links(doc)
        os.rename(doc, f'docs/{doc}')
        print(f"Moved {doc} to docs/{doc}")
