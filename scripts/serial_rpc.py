#!/usr/bin/env python3

from __future__ import annotations

import errno
import fcntl
import os
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_VENV_LIB = REPO_ROOT / ".debug-venv" / "lib"

try:
    import serial  # type: ignore
except ModuleNotFoundError:
    for site_packages in DEBUG_VENV_LIB.glob("python*/site-packages"):
        sys.path.insert(0, str(site_packages))
        break
    import serial  # type: ignore


BAUDRATE = 115200
TIMEOUT_S = 2.5
LOCK_TIMEOUT_S = 5.0
RESET_FALLBACK_VERBS = {"bootloader", "reset"}


def callout_device(device: str) -> str:
    if sys.platform == "darwin" and device.startswith("/dev/tty."):
        return "/dev/cu." + device[len("/dev/tty."):]
    return device


def clean_line(raw: bytes) -> str:
    text = raw.replace(b"\r", b"").decode("utf-8", "ignore")
    text = "".join(ch for ch in text if ch == "\t" or 0x20 <= ord(ch) <= 0x7E)
    return text.strip()


class SerialRPCSession:
    def __init__(self, device: str, timeout_s: float = TIMEOUT_S, log_device: str | None = None):
        self.device = device
        self.port = callout_device(device)
        self.timeout_s = timeout_s
        self.log_device = log_device
        self.handle: serial.Serial | None = None
        self.lock_handle: object | None = None

    def lock_path(self) -> Path:
        safe_name = self.port.replace("/", "_")
        return Path("/tmp") / f"toucan-serial-lock-{safe_name}"

    def acquire_lock(self, timeout_s: float = LOCK_TIMEOUT_S) -> None:
        if self.lock_handle is not None:
            return

        deadline = time.monotonic() + timeout_s
        handle = self.lock_path().open("w")

        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                handle.seek(0)
                handle.truncate()
                handle.write(str(os.getpid()))
                handle.flush()
                self.lock_handle = handle
                return
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                    handle.close()
                    raise
                if time.monotonic() >= deadline:
                    handle.close()
                    raise TimeoutError(f"Timed out waiting for exclusive access to {self.port}")
                time.sleep(0.05)

    def release_lock(self) -> None:
        if self.lock_handle is None:
            return
        try:
            fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.lock_handle.close()
            self.lock_handle = None

    def open(self) -> None:
        if self.handle is not None and self.handle.is_open:
            return

        self.acquire_lock()
        self.handle = serial.Serial(
            self.port,
            BAUDRATE,
            timeout=0.1,
            write_timeout=1.0,
            exclusive=True,
            dsrdtr=False,
            rtscts=False,
            xonxoff=False,
        )
        self.handle.reset_input_buffer()
        self.handle.reset_output_buffer()

    def close(self) -> None:
        if self.handle is None:
            self.release_lock()
            return
        try:
            self.handle.close()
        finally:
            self.handle = None
            self.release_lock()

    def __enter__(self) -> "SerialRPCSession":
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def request_lines(self, payload: str) -> list[str]:
        self.open()
        assert self.handle is not None

        verb = payload.split()[0] if payload.split() else ""
        lines: list[str] = []

        try:
            self.handle.reset_input_buffer()
            self.handle.write((payload + "\n").encode("ascii"))
            self.handle.flush()

            deadline = time.monotonic() + self.timeout_s
            while time.monotonic() < deadline:
                raw = self.handle.readline()
                if not raw:
                    continue
                line = clean_line(raw)
                if not line:
                    continue
                if line.startswith(("OK", "ERR")):
                    lines.append(line)
                    return lines
                if lines:
                    lines.append(line)
        except serial.SerialException:
            if verb in RESET_FALLBACK_VERBS:
                return [f"OK {verb}"]
            raise

        if verb in RESET_FALLBACK_VERBS:
            return [f"OK {verb}"]
        print(f"DEBUG: request_lines returning: {lines}", file=sys.stderr)
        return lines

    def send_async(self, payload: str) -> None:
        """Send a command without waiting for response - for queuing commands"""
        self.open()
        assert self.handle is not None
        
        self.handle.write((payload + "\n").encode("ascii"))
        self.handle.flush()
        # Small delay to ensure command is sent before next one
        time.sleep(0.01)


def request_lines(device: str, payload: str, timeout_s: float = TIMEOUT_S) -> list[str]:
    with SerialRPCSession(device, timeout_s=timeout_s) as session:
        return session.request_lines(payload)


def print_lines(lines: Iterable[str]) -> None:
    for item in lines:
        print(item)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: serial_rpc.py <device> <payload>", file=sys.stderr)
        return 2

    lines = request_lines(sys.argv[1], sys.argv[2])
    print_lines(lines)
    return 0 if any(line.startswith(("OK", "ERR")) for line in lines) else 1


if __name__ == "__main__":
    raise SystemExit(main())
