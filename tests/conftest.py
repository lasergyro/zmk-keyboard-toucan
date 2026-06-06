import pytest
import sys
from toucan_debug.debug_tool import RPCSession

from pad.helpers import reset_touch_state_dual

@pytest.fixture(scope="session")
def rpc_right():
    with RPCSession("right") as rpc:
        # Enable features temporarily so tests can run
        rpc.request("set tap_enable 1 nosave")
        rpc.request("set rclick_enable 1 nosave")
        rpc.request("set drag_enable 1 nosave")
        rpc.request("set scroll_enable 1 nosave")
        yield rpc
        # Wait for any pending BLE input events to transmit before rebooting
        import time
        time.sleep(1.0)
        # Reset right side to clear non-persistent flags
        rpc.request("reset")

@pytest.fixture(scope="session")
def rpc_left():
    with RPCSession("left") as rpc:
        rpc.request("quarantine on")
        yield rpc
        # Wait for any pending BLE input events to transmit before rebooting
        import time
        time.sleep(1.0)
        # Reset left side
        try:
            rpc.request("reset")
        except Exception:
            pass

@pytest.fixture(scope="session")
def params(rpc_right):
    return {
        "tap_timeout_ms": rpc_right.get_pad_param("tap_timeout_ms"),
        "drag_window_timeout_ms": rpc_right.get_pad_param("drag_window_timeout_ms"),
        "drag_pending_timeout_ms": rpc_right.get_pad_param("drag_pending_timeout_ms"),
        "drag_jump_timeout_ms": rpc_right.get_pad_param("drag_jump_timeout_ms"),
        "pad_off_timeout_ms": rpc_right.get_pad_param("pad_off_timeout_ms"),
        "double_click_drag_z_threshold": rpc_right.get_pad_param("double_click_drag_z_threshold")
    }

@pytest.fixture(autouse=True)
def reset_touch_state(rpc_right, rpc_left):
    reset_touch_state_dual(rpc_right, rpc_left)
    yield
