
## RPC Stream Protocol

All four touchpad RPC commands exchange data using the same **event stream format**, sent line by line over the USB serial RPC channel and terminated by a `.` line.

Key code: [[src/debug_rpc.c]].

### Stream Format

Each event is one line:

```
<type>,<delay_ms>,<field1>[,<field2>...]
```

`delay_ms` is the delay **before** the event:
- On playback: `wait(delay_ms)` then inject event
- On recording: `delta_time_since_last_event` stored as delay

### Input Event Types (PC→firmware, or `rend` firmware→PC)

| Code | Type | Fields | Description |
|------|------|--------|-------------|
| `A` | abs | `x,y,z` | Absolute position (1024×1024 pad, z=pressure) |
| `K` | key | `code,value` | Key/button event; `code` is numeric (e.g. 330=BTN_TOUCH); value: 0=up 1=down |

### Output Event Types (firmware→PC via `pad_qo`)

| Code | Type | Fields | Description |
|------|------|--------|-------------|
| `M` | move | `dx,dy` | Cursor delta |
| `S` | scroll | `axis,value` | Scroll; axis: 0=horizontal 1=vertical |
| `K` | key | `code,value` | Key/button; `code` is numeric (e.g. 272=BTN_0/left, 273=BTN_1/right); value: 0=up 1=down |

### Commands

#### `qi` — Queue Input
PC sends a stream of input events; firmware stores them in the scenario queue.
```
PC → FW:  qi
FW → PC:  (ready — firmware enters stream-receive mode)
PC → FW:  A,0,512,512,50
PC → FW:  A,10,552,512,50
PC → FW:  K,30,330,0
PC → FW:  .
FW → PC:  OK qi 3
```

#### `qo` — Queue Output (execute + retrieve)
Firmware executes the queued input events with firmware-accurate timing, captures all output events emitted during execution, then streams them back. Also serves as implicit queue clear (calling with empty queue drains/resets state).
```
PC → FW:  qo
FW → PC:  M,5,-40,0
FW → PC:  K,120,272,1
FW → PC:  K,5,272,0
FW → PC:  .
FW → PC:  OK qo 3
```

#### `rstart` — Record Start
Firmware begins recording real Pinnacle input events into an internal ring buffer (same format as `qi` stream).
```
PC → FW:  rstart
FW → PC:  OK rstart
```

#### `rend` — Record End
Firmware stops recording and streams the captured input events back to the PC.
```
PC → FW:  rend
FW → PC:  A,0,511,509,48
FW → PC:  A,9,512,511,49
FW → PC:  A,11,513,512,50
FW → PC:  .
FW → PC:  OK rend 3
```

---

## Full RPC Command Reference

| Command | Description |
|---------|-------------|
| `ping` | Returns identity (side, role, quarantine) |
| `identity` | Same as ping |
| `reset` | Cold reboot |
| `bootloader` | Enter UF2 bootloader |
| `quarantine <on\|off\|status>` | Suppress HID output (captures in log instead) |
| `layers` | Returns the active layer state bitmask. Central half only. |
| `get [param]` | Get touchpad gesture tuning parameter (or list all if no param). Right half only. |
| `set <param> <value>` | Set and persist touchpad gesture tuning parameter. Right half only. |
| `key <pos> <down\|up>` | Inject key position event |
| `tap <pos>` | Quick key press+release |
| `touch <down\|up>` | Inject BTN_TOUCH event (manual debug) |
| `abs <x> <y> [z]` | Inject ABS_X + ABS_Y + Z pair (manual debug) |
| `move <dx> <dy>` | Inject REL_X + REL_Y pair (manual debug) |
| `qi` | Stream input events into scenario queue |
| `qo` | Execute queue, stream output events back |
| `rstart` | Start recording real Pinnacle input |
| `rend` | Stop recording, stream captured events back |
| `help` | List commands |

---
