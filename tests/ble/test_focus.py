import subprocess
import time

def check_focus():
    result = subprocess.run(
        ["defaults", "read", "com.apple.ncprefs.plist"],
        capture_output=True, text=True
    )
    return result.stdout

print(check_focus())
