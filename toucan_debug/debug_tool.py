#!/usr/bin/env python3

from __future__ import annotations

import glob
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable

from .serial_rpc import SerialRPCSession, request_lines, serial


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = Path(os.environ.get("LOG_DIR", REPO_ROOT / "debug-logs"))
TIMESTAMP_RE = re.compile(r"^\[[0-9][0-9]:")
ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_PAREN_RE = re.compile(r"\x1b[\(\)][0-9A-Za-z]")
ANSI_SINGLE_RE = re.compile(r"\x1b[@-Z\\-_]")
CONTROL_RE = re.compile(r"[\x00-\x07\x0B-\x1F\x7F]")
STOP_LOGS = False


@dataclass
class DeviceInfo:
    path: str
    dev_type: str = "unknown"
    side: str = "unknown"
    role: str = "unknown"
    location: str = "unknown"
    interface: str = "unknown"
    quarantine: str = "unknown"


@dataclass
class LogStream:
    device: str
    label: str
    clean_path: Path
    serial_session: SerialRPCSession | None = None
    file_handle: object | None = None
    pending: str = ""


def die(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def log(message: str) -> None:
    print(f"==> {message}")


def request_stop(signum: int, frame) -> None:
    global STOP_LOGS
    STOP_LOGS = True


def ensure_command(name: str) -> None:
    if not shutil_which(name):
        raise SystemExit(die(f"Required command not found: {name}"))


def shutil_which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory) / name
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def list_candidate_devices() -> list[str]:
    return sorted(device for device in glob.glob("/dev/tty.usbmodem*") if Path(device).exists())


def parse_ioreg_metadata() -> dict[str, tuple[str, str]]:
    try:
        output = subprocess.check_output(
            ["ioreg", "-r", "-c", "IOUSBHostInterface", "-l"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return {}

    metadata: dict[str, tuple[str, str]] = {}
    location = ""
    interface = ""

    for line in output.splitlines():
        match = re.search(r'"locationID"\s+=\s+(\d+)', line)
        if match:
            location = match.group(1)
            continue

        match = re.search(r'"bInterfaceNumber"\s+=\s+(\d+)', line)
        if match:
            interface = match.group(1)
            continue

        match = re.search(r'"IODialinDevice"\s+=\s+"([^"]+/tty\.usbmodem[^"]+)"', line)
        if match and location and interface:
            metadata[match.group(1)] = (location, interface)
            location = ""
            interface = ""

    return metadata


def identity_field(response: str, key: str) -> str:
    match = re.search(rf"{re.escape(key)}=([A-Za-z0-9_-]+)", response)
    return match.group(1).lower() if match else "unknown"


def ping_response(device: str, log_device: str | None = None) -> str:
    try:
        lines = request_lines(device, "ping")
    except Exception:
        return ""

    response = "\n".join(lines)
    return response if response.startswith("OK pong") else ""


def inventory(include_runtime_probe: bool = False) -> list[DeviceInfo]:
    devices = list_candidate_devices()
    if not devices:
        return []

    metadata = parse_ioreg_metadata()
    grouped: Dict[str, list[DeviceInfo]] = {}
    info_by_path: Dict[str, DeviceInfo] = {}

    for device in devices:
        location, interface = metadata.get(device, ("unknown", "unknown"))
        info = DeviceInfo(path=device, location=location, interface=interface)
        info_by_path[device] = info
        group_key = location if location != "unknown" else f"device:{Path(device).name}"
        grouped.setdefault(group_key, []).append(info)

    for group in grouped.values():
        by_iface = {info.interface: info for info in group}
        rpc_device: DeviceInfo | None = None
        log_device: DeviceInfo | None = None

        response = ""
        studio_device: DeviceInfo | None = None

        if "1" in by_iface and "4" in by_iface and "6" in by_iface:
            # Left debug build with separate Studio/log/rpc CDC ACM devices.
            # Interface layout: studio-rpc-usb-uart(comm=0,data=1), HID(2),
            #   zmk-usb-logging(comm=3,data=4), toucan-debug-rpc(comm=5,data=6).
            studio_device = by_iface["1"]
            log_device = by_iface["4"]
            rpc_device = by_iface["6"]
            side = "left"
            role = "central"
        elif "1" in by_iface and "4" in by_iface:
            # Left debug build (legacy: studio and log share the same two slots,
            # debug RPC was on the studio UART before the split).
            rpc_device = by_iface["1"]
            log_device = by_iface["4"]
            side = "left"
            role = "central"
        elif "1" in by_iface and "3" in by_iface:
            rpc_device = by_iface["3"]
            log_device = by_iface["1"]
            side = "right"
            role = "peripheral"
        else:
            for info in group:
                peer = next((other for other in group if other.path != info.path), None)
                response = ping_response(info.path, peer.path if peer else None)
                if response:
                    rpc_device = info
                    break
            if rpc_device:
                side = identity_field(response, "side")
                role = identity_field(response, "role")
                log_device = next((info for info in group if info.path != rpc_device.path), None)
            else:
                side = "unknown"
                role = "unknown"

        quarantine = "unknown"
        if rpc_device:
            rpc_device.dev_type = "rpc"
            rpc_device.side = side
            rpc_device.role = role

            if include_runtime_probe and not response:
                response = ping_response(rpc_device.path, log_device.path if log_device else None)

            if response:
                side = identity_field(response, "side") if side == "unknown" else side
                role = identity_field(response, "role") if role == "unknown" else role
                quarantine = identity_field(response, "quarantine")
                rpc_device.side = side
                rpc_device.role = role
                rpc_device.quarantine = quarantine

        if studio_device:
            studio_device.dev_type = "studio"
            studio_device.side = side
            studio_device.role = role

        if log_device:
            log_device.dev_type = "log"
            log_device.side = side
            log_device.role = role
            log_device.quarantine = quarantine

    return [info_by_path[path] for path in devices]


def print_devices(args: list[str]) -> int:
    include_runtime_probe = "--probe" in args
    devices = inventory(include_runtime_probe=include_runtime_probe)
    if not devices:
        print("No /dev/tty.usbmodem* devices found.")
        return 0

    for info in devices:
        extra = f" quarantine={info.quarantine}" if info.quarantine != "unknown" else ""
        print(
            f"{info.path} type={info.dev_type} side={info.side} role={info.role}"
            f"{extra} location={info.location} iface={info.interface}"
        )
    return 0


def select_device(dev_type: str, selector: str | None) -> DeviceInfo:
    devices = [info for info in inventory(include_runtime_probe=False) if info.dev_type == dev_type]
    if selector and selector.startswith("/dev/"):
        for info in inventory(include_runtime_probe=False):
            if info.path == selector:
                return info
        raise SystemExit(die(f"Requested device does not exist: {selector}"))

    if selector in {"left", "right"}:
        matches = [info for info in devices if info.side == selector]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise SystemExit(die(f"Unable to find a {dev_type} device for side '{selector}'"))
        raise SystemExit(die(f"Multiple {dev_type} devices matched side '{selector}'"))

    if selector:
        raise SystemExit(die(f"Unknown device selector: {selector}"))

    if len(devices) == 1:
        return devices[0]
    if not devices:
        raise SystemExit(die(f"No /dev/tty.usbmodem* {dev_type} devices found"))
    raise SystemExit(
        die(
            f"Multiple {dev_type} devices found: {' '.join(info.path for info in devices)}. "
            f"Specify left, right, or an explicit /dev/tty.usbmodem path."
        )
    )


def paired_device(source: DeviceInfo, dev_type: str) -> DeviceInfo:
    devices = inventory(include_runtime_probe=False)

    if source.side != "unknown":
        matches = [info for info in devices if info.dev_type == dev_type and info.side == source.side]
        if len(matches) == 1:
            return matches[0]

    matches = [
        info
        for info in devices
        if info.dev_type == dev_type and info.location == source.location and info.path != source.path
    ]
    if len(matches) == 1:
        return matches[0]

    raise SystemExit(
        die(f"Unable to find paired {dev_type} device for {source.path}")
    )


def send_rpc(args: list[str]) -> int:
    if not args:
        return die("Missing RPC command. Use ./debug.sh rpc [left|right|device] <command>")

    selector = None
    if args[0] in {"left", "right"} or args[0].startswith("/dev/"):
        selector = args[0]
        args = args[1:]

    if not args:
        return die("Missing RPC command. Use ./debug.sh rpc [left|right|device] <command>")

    device = select_device("rpc", selector)
    payload = " ".join(args)
    log(f"Sending RPC '{payload}' to {device.path}")
    try:
        session = SerialRPCSession(device.path, timeout_s=5.0)
        session.open()
        try:
            lines = session.request_lines(payload)
        finally:
            session.close()
    except TimeoutError as exc:
        return die(str(exc))
    except Exception as exc:
        return die(f"RPC failed on {device.path}: {exc}")
    if lines:
        for line in lines:
            print(line)
    return 0 if any(line.startswith(("OK", "ERR")) for line in lines) else 1


def clean_text(text: str) -> str:
    text = text.replace("\r", "")
    text = ANSI_CSI_RE.sub("", text)
    text = ANSI_PAREN_RE.sub("", text)
    text = ANSI_SINGLE_RE.sub("", text)
    text = text.replace("\x08", "")
    text = CONTROL_RE.sub("", text)
    return text


def log_file_path(device: str, label: str = "", timestamp: str = "") -> Path:
    stamp = timestamp or time.strftime("%Y%m%d-%H%M%S")
    suffix = f"-{label}" if label else ""
    return LOG_DIR / f"{stamp}{suffix}-{Path(device).name}.log"


def start_log_stream(stream: LogStream) -> None:
    stream.serial_session = SerialRPCSession(stream.device, timeout_s=0.1)
    stream.serial_session.open()
    assert stream.serial_session.handle is not None
    stream.serial_session.handle.reset_input_buffer()
    stream.file_handle = stream.clean_path.open("w", encoding="utf-8")


def stop_log_stream(stream: LogStream) -> None:
    if stream.serial_session is not None:
        stream.serial_session.close()
        stream.serial_session = None
    if stream.file_handle is not None:
        # pyrefly: ignore [missing-attribute]
        stream.file_handle.close()
        stream.file_handle = None


def emit_log_line(stream: LogStream, text: str) -> None:
    if stream.label:
        sys.stdout.write(f"[{stream.label}] {text}\n")
    else:
        sys.stdout.write(text + "\n")
    sys.stdout.flush()
    if stream.file_handle is not None:
        # pyrefly: ignore [missing-attribute]
        stream.file_handle.write(text + "\n")
        # pyrefly: ignore [missing-attribute]
        stream.file_handle.flush()


def follow_logs(streams: list[LogStream]) -> None:
    global STOP_LOGS
    STOP_LOGS = False
    try:
        while not STOP_LOGS:
            active_streams = 0
            for stream in streams:
                if stream.serial_session is None or stream.serial_session.handle is None:
                    continue
                active_streams += 1
                try:
                    raw = stream.serial_session.handle.readline()
                except (serial.SerialException, OSError) as exc:
                    log(f"{stream.label or Path(stream.device).name} serial stream ended: {exc}")
                    stop_log_stream(stream)
                    continue
                if not raw:
                    continue
                text = clean_text(raw.decode("utf-8", "ignore"))
                if not text:
                    continue
                stream.pending = ""
                emit_log_line(stream, text)

            if active_streams == 0:
                break
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        for stream in streams:
            stop_log_stream(stream)
            log(f"Saved cleaned {stream.label or Path(stream.device).name} serial log to {stream.clean_path}")


def build_log_stream(device: DeviceInfo, label: str, timestamp: str) -> LogStream:
    clean_path = log_file_path(device.path, label, timestamp)
    return LogStream(
        device=device.path,
        label=label,
        clean_path=clean_path,
    )


def open_logs(args: list[str]) -> int:
    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    if args and args[0] == "both":
        streams = [
            build_log_stream(select_device("log", "left"), "left", timestamp),
            build_log_stream(select_device("log", "right"), "right", timestamp),
        ]
    else:
        selector = args[0] if args else None
        streams = [build_log_stream(select_device("log", selector), "", timestamp)]

    for stream in streams:
        label_text = f"{stream.label} " if stream.label else ""
        log(f"Writing {label_text}serial log to {stream.clean_path}")
        start_log_stream(stream)

    log("Following logs (exit with Ctrl-C)")
    try:
        follow_logs(streams)
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
    return 130 if STOP_LOGS else 0


def usage() -> int:
    print(
        "\n".join(
            [
                "Usage: ./debug.sh [command]",
                "",
                "Commands:",
                "  build     Build debug firmware into artifacts/debug.",
                "  devices   List Toucan USB CDC ACM devices on macOS and annotate rpc/log roles.",
                "            Pass --probe to also query live RPC metadata.",
                "  logs      Open one or both log streams and capture timestamped files.",
                "  rpc       Send a debug RPC command over the USB CDC ACM RPC port.",
                "  inject    Convenience wrapper for debug-only input injection commands.",
                "  help      Show this help text.",
            ]
        )
    )
    return 0


class RPCSession:
    """Clean abstraction for automated tests to communicate with firmware."""
    def __init__(self, selector: str = "left", timeout: float = 5.0):
        self.device = select_device("rpc", selector)
        self.session = SerialRPCSession(self.device.path, timeout_s=timeout)

    def __enter__(self) -> RPCSession:
        self.session.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def get_pad_param(self, key: str) -> int:
        lines = self.request(f"get {key}")
        for line in lines:
            if line.startswith(f"OK {key}="):
                return int(line.split("=")[1])
        raise RuntimeError(f"Failed to get {key}")

    def request(self, command: str) -> list[str]:
        """Send a command and return all response lines."""
        return self.session.request_lines(command)

    def run_scenario(self, scenario: list[str]) -> list[str]:
        """Queue and execute a scenario via qi/qo."""
        handle = self.session.handle
        assert handle is not None
        
        # 1. Queue scenario
        handle.write(b"qi\n")
        handle.flush()
        ready_line = handle.readline().decode("utf-8", "ignore").strip()
        
        for line in scenario:
            handle.write(line.encode("utf-8") + b"\n")
            handle.flush()
            # Wait for ACK
            ack = handle.readline().decode("utf-8", "ignore").strip()
            if not ack.startswith("OK qi"):
                raise RuntimeError(f"Failed to queue line '{line}', got: '{ack}'")
                
        handle.write(b".\n")
        handle.flush()
        
        # Wait for done ACK
        done_ack = handle.readline().decode("utf-8", "ignore").strip()
        if not done_ack.startswith("OK qi done"):
            raise RuntimeError(f"Failed to complete queueing, got: '{done_ack}'")
        
        # 2. Execute and capture
        handle.write(b"qo\n")
        handle.flush()
        
        output = []
        # Wait up to 10s for the scenario to finish and stream back results
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            line = handle.readline().decode("utf-8", "ignore").strip()
            if not line:
                continue
            if "OK qo" in line:
                break
            if line != ".":
                output.append(line)
            
        return output


def main(argv: Iterable[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)
    command = args[0] if args else "help"
    command_args = args[1:]

    if command in {"help", "-h", "--help"}:
        return usage()
    if command == "devices":
        return print_devices(command_args)
    if command == "logs":
        return open_logs(command_args)
    if command in {"rpc", "inject"}:
        return send_rpc(command_args)

    return die(f"Unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
