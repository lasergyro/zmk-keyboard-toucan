# Global Claude Notes

## macOS — Removable Volume Access

When flashing UF2 firmware to devices (e.g. XIAO nRF52840 in bootloader mode), macOS requires explicit UI authorization before the Claude process can access newly-mounted removable volumes. The volume may appear in `/Volumes/` but `cp` or other write operations will silently fail or appear to hang until the user approves the access prompt.

**What this looks like in practice:** The UF2 bootloader volume (e.g. `/Volumes/XIAO-BOOT`) mounts correctly, but the `cp` command blocks or fails until macOS shows the user a permission dialog. The user must approve it for the copy to proceed.

**Workaround:** Ask the user to watch for and approve the macOS removable-volume access prompt when a copy to a freshly-mounted UF2 volume is in flight. Alternatively, pre-grant `Full Disk Access` to the terminal/process.
