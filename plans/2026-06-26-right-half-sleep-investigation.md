# Right-half deep-sleep investigation + persistent sleep statistics proposal

**Date:** 2026-06-26
**Suspicion:** The right half is not entering deep sleep properly (stays awake too long).
**Status:** Code inspection complete. No flashing/measurement done yet — this is a static analysis plus a concrete telemetry proposal to confirm/deny it on hardware.

Related prior work: [2026-05-29-deep-sleep-fix.md](2026-05-29-deep-sleep-fix.md) (wake-from-sleep fix that removed `CONFIG_ZMK_PM_SOFT_OFF`).

---

## 1. How sleep actually works on this keyboard

### 1.1 Two independent per-half timers

Sleep is driven entirely by ZMK's activity subsystem, [external/zmk/app/src/activity.c](../external/zmk/app/src/activity.c). **Each half runs its own copy** of this code with its own `activity_last_uptime` and its own 1-second timer. There is **no cross-half keep-alive**: the central never tells the peripheral "stay awake", and vice-versa. Each half decides to sleep based only on *its own* activity.

The expiry handler ([activity.c:74-94](../external/zmk/app/src/activity.c#L74-L94)):

```c
int32_t inactive_time = current - activity_last_uptime;
if (inactive_time > MAX_SLEEP_MS && !is_usb_power_present()) {   // 3600000 ms = 60 min
    set_state(ZMK_ACTIVITY_SLEEP);
    zmk_pm_suspend_devices();
    sys_poweroff();                 // System OFF — full power-down, wakes via reset
} else if (inactive_time > MAX_IDLE_MS) {   // 30000 ms = 30 s
    set_state(ZMK_ACTIVITY_IDLE);
}
```

So a half deep-sleeps only when **all three** hold:
1. 60 minutes since its last activity event, AND
2. it is **not** powered over USB (`!is_usb_power_present()`), AND
3. the 1 Hz timer fires while both above are true.

### 1.2 What counts as "activity" — and the right-half twist

`activity_last_uptime` is reset to "now" (`note_activity()`) by three sources:

- **`zmk_position_state_changed`** — key presses. On the right half these are *its own* matrix keys only (key events flow peripheral→central, never the reverse). ([activity.c:110](../external/zmk/app/src/activity.c#L110))
- **`zmk_sensor_event`** — not used here.
- **Any input subsystem event** via `INPUT_CALLBACK_DEFINE(NULL, activity_input_listener)` — gated on `CONFIG_ZMK_POINTING`, which is `=y` on both halves. ([activity.c:113-123](../external/zmk/app/src/activity.c#L113-L123))

The `NULL` device means **every input event from any driver resets the timer**. On the right half, the Cirque/Pinnacle trackpad lives on this half, so **every touchpad input event resets the right half's 60-minute clock.** This is the key asymmetry: the right half's wake state is coupled to the trackpad, the left half's is not.

### 1.3 Does the trackpad spam events while idle? (No — when healthy)

The Pinnacle driver is interrupt-driven off the DR (data-ready) GPIO, and only calls `input_report_*` on a *change*: button edges, a new touch contact, a lift edge, or movement while touching ([input_pinnacle.c:290-338](../external/cirque-input-module/drivers/input/input_pinnacle.c#L290-L338), abs path at [340-382](../external/cirque-input-module/drivers/input/input_pinnacle.c#L340-L382)). With no finger and a clean sensor, DR does not assert, so **no input events are emitted and the timer is free to expire.** A healthy idle pad does *not* keep the half awake.

This matters: it means "right half awake too long" is **not** an inherent design flaw of a quiet pad. It points at *spurious* events (see §2).

### 1.4 The device-suspend path IS correctly wired

When the right half does reach `sys_poweroff()`, `zmk_pm_suspend_devices()` ([external/zmk/app/src/pm.c:30-64](../external/zmk/app/src/pm.c#L30-L64)) walks all devices and runs `PM_DEVICE_ACTION_SUSPEND`. For the Pinnacle that calls `pinnacle_set_shutdown(dev, true)` ([input_pinnacle.c:1246-1257](../external/cirque-input-module/drivers/input/input_pinnacle.c#L1246-L1257)), powering the sensor down.

Crucially, this works **without** `CONFIG_ZMK_PM_SOFT_OFF`: `CONFIG_ZMK_SLEEP` already `select`s `ZMK_PM_DEVICE_SUSPEND_RESUME` ([external/zmk/app/Kconfig:396-400](../external/zmk/app/Kconfig#L396-L400)), which `select`s `ZMK_PM`. **The comment in `toucan_right.conf` (and `toucan_left.conf`) claiming we need SOFT_OFF "to get proper sleep notifications into the cirque driver" is outdated/misleading** — SOFT_OFF was removed in the 2026-05-29 fix precisely because it broke wake-up, and the suspend notifications still flow. Worth correcting that comment so a future reader doesn't re-enable SOFT_OFF.

The kscan matrix has `wakeup-source` ([toucan.dtsi:20](../boards/shields/toucan/toucan.dtsi#L20)), so `zmk_pm_suspend_devices()` skips it (`pm_device_wakeup_is_enabled`) and it remains armed to wake the half on a physical keypress. The trackpad is deliberately **not** a wake source.

---

## 2. Why the right half might "stay awake too long" — ranked hypotheses

Given §1.3, a quiet pad sleeps fine. So the awake-too-long symptom most likely comes from something repeatedly resetting the timer at intervals shorter than 60 min. Ranked:

1. **Spurious / phantom trackpad events (most likely).** Electrical noise, marginal grounding, a recalibration that registers a contact+lift, or DR glitches each produce an input event → `note_activity()` → 60-min clock restarts. A single phantom event every <60 min keeps the half awake **indefinitely**. Note even a finger-lift emits a `BTN_TOUCH=0` event ([input_pinnacle.c:330](../external/cirque-input-module/drivers/input/input_pinnacle.c#L330)), so one noise blip that reads as touch-then-lift is *two* activity resets.

2. **USB power present.** If the right half is plugged into USB (e.g. left connected during debugging, or a charger), `is_usb_power_present()` is true and it will **never** deep-sleep — only drop to IDLE. Easy to overlook when measuring.

3. **A stuck or bouncing right-half matrix key** generating periodic `position_state_changed` events.

4. **Misattributed expectation.** Because key events are peripheral→central only, the right half's clock is *not* reset when you type on the left half. So during left-only typing the right half should sleep *earlier* than the left — the opposite of the suspicion. If you expected the halves to sleep together, the right sleeping "independently" can look wrong in either direction.

**We cannot currently distinguish these on hardware** — there is no record of *why* or *how long* each half stayed awake. That is exactly what the statistics proposal below is for.

### Quick confirmation (before building telemetry)

Use the rapid-sleep technique from the prior plan: temporarily set `CONFIG_ZMK_IDLE_SLEEP_TIMEOUT=15000` in `toucan_right.conf`, build debug, and watch the right half's own log (`./debug.sh logs right`) on battery (USB **unplugged** from the right half). If it never logs `sys_poweroff`, raise `CONFIG_INPUT_LOG_LEVEL` to DBG and watch for `abs:`/`Rel move:` lines appearing with no finger on the pad — that confirms hypothesis #1.

---

## 3. Proposal: persistent per-half sleep statistics

**Goal:** for each half independently, record enough to answer "was this half awake because it was used, or was it kept awake spuriously?" — and have it survive deep sleep (which is a full power-down + reboot).

### 3.1 Constraints that shape the design

- **Deep sleep wipes RAM.** `sys_poweroff()` is System OFF; the half reboots on wake. Counters must be flushed to non-volatile storage **before** power-down.
- **There is a clean flush hook.** `set_state(ZMK_ACTIVITY_SLEEP)` raises `zmk_activity_state_changed` *synchronously* (ZMK event dispatch runs in the caller's thread) and this happens **before** `zmk_pm_suspend_devices()`/`sys_poweroff()` in [activity.c:80-88](../external/zmk/app/src/activity.c#L80-L88). A `ZMK_SUBSCRIPTION(...)` listener on that event can persist stats and is guaranteed to run before the chip powers off.
- **NVS has write-wear limits**, so we persist coarsely (on sleep entry + boot increment), not continuously.
- **Each half already has its own settings/NVS** and its own debug RPC channel over USB (`./debug.sh devices` lists `right rpc`). We can read each half's stats directly without inventing a split protocol.
- Existing persistence pattern to mirror: `SETTINGS_STATIC_HANDLER_DEFINE` + `settings_save_one()` in [src/debug_rpc.c:574](../src/debug_rpc.c#L574) and [src/toucan_text_state.c:300](../src/toucan_text_state.c#L300).

### 3.2 New module: `src/toucan_sleep_stats.c` (built into **both** halves)

State kept in RAM and accumulated from events:

- `session_start_uptime` — set at boot.
- `session_active_ms`, `session_idle_ms` — accumulated as the half transitions ACTIVE↔IDLE (timestamp deltas on each `zmk_activity_state_changed`).
- `session_key_events`, `session_input_events` — **the diagnostic pair.** Increment from two cheap listeners:
  - `session_key_events`: `ZMK_SUBSCRIPTION(..., zmk_position_state_changed)`.
  - `session_input_events`: an `INPUT_CALLBACK_DEFINE(NULL, ...)` mirroring activity.c, counting trackpad/input events (the suspected noise source). On the right half this directly measures "how many times did the pad poke the activity timer".
- `idle_to_active_count` — increments on an IDLE→ACTIVE transition (how many times the half was re-woken from idle within a session).

Persisted to settings namespace `toucan/sleep/*` (u32 unless noted):

| key | meaning |
|-----|---------|
| `boot_count` | +1 each boot (a deep-sleep wake is a reboot, so ≈ wakes + manual resets) |
| `sleep_entries` | lifetime count of `sys_poweroff` deep-sleeps actually reached |
| `cum_awake_ms` (u64) | lifetime awake (active+idle) time |
| `cum_key_events` / `cum_input_events` | lifetime counters — ratio reveals use-vs-noise |
| `last_session_awake_ms` | awake duration of the session that just ended |
| `last_session_key_events` / `last_session_input_events` | per-session breakdown of the session that just ended |
| `last_exit` | enum: `0=clean_sleep`, `1=reboot/other` (set to `1` early at boot, overwritten to `0` only on the sleep-entry flush — lets you tell deep-sleeps from crashes/manual resets) |

**Write strategy (wear-aware):**
- On boot: load all keys, increment `boot_count`, write `last_exit=1` (assume non-clean until proven otherwise), commit once.
- On `zmk_activity_state_changed → SLEEP`: fold the session counters into the `cum_*` totals, write the `last_session_*`, increment `sleep_entries`, set `last_exit=0`, then return so activity.c proceeds to power off. (One NVS write burst per real sleep — low wear.)
- No per-transition NVS writes; ACTIVE/IDLE deltas only accumulate in RAM.

### 3.3 Readout

- **Per-half over USB RPC (primary, for diagnosis):** add a `sleepstats` command to the debug RPC ([src/debug_rpc.c](../src/debug_rpc.c)) that dumps the live RAM counters + persisted totals as a struct/JSON line. Because each half exposes its own RPC over USB in debug builds, run it against the **right** half directly to see whether its awake time is dominated by `input_events` (noise) or `key_events` (use). This needs no split protocol.
- **Optional glance value:** surface a tiny "awake h:m since boot" or sleep-entry count on the right half's nice_view display (the screen already subscribes to `zmk_activity_state_changed`, [widgets/screen.c:7](../boards/shields/nice_view_gem/widgets/screen.c#L7)).
- **Optional later:** proxy the right half's persisted stats to the central over a split GATT service (same mechanism as the peripheral battery proxy) so they can be read without a USB cable on the right half. Deferred — the per-half USB RPC covers the immediate diagnostic need.

### 3.4 How this answers the original question

Compare, per half, `cum_awake_ms` against `cum_key_events + cum_input_events`:
- **High awake time, low key events, high input events on the right half** → the trackpad is keeping it awake (hypothesis #1 confirmed). Next step: enable `CONFIG_ZMK_INPUT_PINNACLE_IDLE_SLEEPER` and/or chase the noise source.
- **High awake time tracking high key/input events** → it matched real use; nothing wrong.
- **`sleep_entries` near zero with `boot_count` climbing** → it's rebooting/resetting rather than cleanly sleeping (check USB-power hypothesis #2 and wake reliability).

---

## 3b. Can we keep a rotating *log* (durations of sleep/active + charging) over ~2 days?

Short answer: **yes in RAM (easily), no in NVS for the full-rate log.** Use a two-tier design.

### Memory facts (XIAO nRF52840, measured from the build)

- **NVS / settings partition is only 32 KB** (`storage_partition` `0xec000–0xf4000`, [xiao_ble_common.dtsi:164-166](../.zmk-workspace/zephyr/boards/arm/xiao_ble/xiao_ble_common.dtsi)) and is **shared** with BLE bonds, endpoint selection, text-output mode, and touchpad params. It is wear-leveled key-value over 4 KB flash pages — *not* a natural ring/log, and high-rate appends here would churn the same area the BLE bonds live in.
- **RAM is abundant.** The right-half image uses ~43 KB static RAM (`_end = 0x2000aaa4`) of the 256 KB region → **~213 KB free**. A multi-KB ring buffer is trivially affordable on both halves.
- **A dedicated flash log partition is not worth it.** The firmware has unused tail (right ~283 KB, left ~478 KB of 788 KB), but the 1 MB map is fully allocated, so a log partition must be carved out of `code_partition`. UF2 *flashing* itself wouldn't break (the app stays linked at `0x27000`), but it's a global board-DTS change that cuts firmware headroom, risks invalidating NVS/BLE bonds if the `storage` boundary moves, and needs a new raw-flash log layer — high effort, low upside. Use the existing NVS instead (§3c).

### Event volume over 2 days

Transitions are bounded: ACTIVE↔IDLE is paced by the 30 s idle timeout (a burst of use + a ≥30 s pause = one cycle), plus rare SLEEP entries and a handful of charge/USB plug-unplug edges per day. Realistic worst case is a few hundred transitions/day → **order 10²–10³ records over 2 days.**

At `{ uint32 duration_ms; uint8 type; }` packed to 8 B/record:
- 1024 entries = **8 KB** (≈ covers 2 days at ~hundreds/day)
- 2048 entries = **16 KB** (comfortable margin)

Both fit in the ~213 KB of free RAM with room to spare.

RAM is abundant but `sys_poweroff()` wipes it on every deep sleep, so a RAM ring loses everything each time a battery-powered half sleeps. **Decision (per follow-up): the log must be persistent — RAM-only is out. It has to live in the 32 KB NVS.** The rest of this section works out how to do that without thrashing flash or crowding the BLE bonds.

## 3c. Encoding the log in NVS

### How NVS actually stores things (the cost model that drives the encoding)

Backend is `CONFIG_SETTINGS_NVS` over the 32 KB `storage` partition. Measured facts from this tree:

- **Geometry:** sector size = `SECTOR_SIZE_MULT(1) × FLASH_ERASE_BLOCK_SIZE(4096)` = 4 KB; sector count = 8 (default, capped by the 32 KB partition) → **8 sectors × 4 KB**. ([settings_nvs.c:350-383](../.zmk-workspace/zephyr/subsys/settings/src/settings_nvs.c#L350-L383))
- **NVS keeps one sector free for garbage collection**, so the practical ceiling for *live* data is ≈ **7 sectors ≈ 28 KB**, not 32.
- **Every NVS entry costs `align4(len) + 8`**: the data is written aligned to the 4-byte write-block, plus a fixed **8-byte ATE** (`struct nvs_ate`, [nvs_priv.h:34-40](../.zmk-workspace/zephyr/subsys/fs/nvs/nvs.c)). There is **no inline-small-data optimization** in this version — `nvs_flash_wrt_entry` always writes data *and* an ATE ([nvs.c:402-425](../.zmk-workspace/zephyr/subsys/fs/nvs/nvs.c#L402-L425)). So a 2-byte value still consumes `4 + 8 = 12` bytes of log.
- **The settings layer stores each key as TWO NVS entries** — a *name* entry (the full key string) and a *value* entry ([settings_nvs.c:194-273](../.zmk-workspace/zephyr/subsys/settings/src/settings_nvs.c#L194-L273)). The name is written once when the key is first created and reused; updates rewrite only the value.

Three consequences for encoding:
1. **Long key names are expensive but one-time.** `toucan/pad/scroll_exclusion_zone_percent` burns `align4(40)+8 = 48 B` just for the name. → **use short keys** for anything we add (`tsl/0`, not `toucan/sleep/log/page/0`).
2. **The 8-byte ATE dominates tiny values.** Writing one 2-byte record per NVS entry wastes 80% on overhead. → **batch many records into one value** (a "page") to amortize.
3. **Write frequency = flash wear.** Each rewrite churns the log toward a GC/erase. → **flush on page-fill + critical events, not on every transition.**

### How much of the 32 KB is free?

Estimate (precise value is measurable — see below). Live consumers:
- **This repo:** 14 `toucan/pad/*` keys ≈ name(~48 B)+value(12 B) each ≈ **~840 B**; `toucan_text/*` modes ≈ **~200 B**. ≈ **~1 KB**.
- **ZMK + BLE bonds (the big one):** endpoint/profile state plus per-peer bond keys (`bt/keys`, `bt/ccc`, `bt/irk`, `bt/sc`, …). On the **central** with several host profiles + the split bond this is typically **~2–4 KB**; on the **peripheral** (one bond to the central) it's far less.

So a realistic picture: **~3–5 KB used on the central, leaving ~23–25 KB free; the peripheral has ~25–27 KB free** — all relative to the ~28 KB live ceiling. **Plenty for a log on either half.**

> Measure it exactly: `nvs_calc_free_space()` exists in this Zephyr ([nvs.h:163](../.zmk-workspace/zephyr/include/zephyr/fs/nvs.h#L163), [nvs.c:1216](../.zmk-workspace/zephyr/subsys/fs/nvs/nvs.c#L1216)). Add a one-line `nvsfree` debug-RPC command that calls it on the settings `nvs_fs` and returns the byte count — then read the true free space per half over USB. No repartitioning, ~10 lines.

### Recommended encoding: compact records in a page-ring

**Record = 2 bytes** (`uint16`): 3 bits state (`ACTIVE/IDLE/SLEEP` ×2 bits + `charging` ×1 bit) + 13 bits duration in seconds (0–8191 s ≈ 2.3 h; cap — deep sleep cuts in at 60 min, so 13 bits is more than enough and the SLEEP record ends an awake run anyway). Lossless to 1-second resolution. (A 1-byte variant — 3 bits state + 5 bits log-quantized duration — halves the size if needed, at the cost of duration precision.)

**Container = a ring of N short-named keys**, each holding a packed *page* of records:
- e.g. **P = 24 keys** `tsl/0`…`tsl/23`, each a value of **2 B header (page sequence + record count) + 42 records × 2 B = 86 B**. Capacity = 24 × 42 = **1008 records ≈ 2+ days** at a few hundred transitions/day.
- **NVS footprint:** value set = 24 × (align4(86)+8 = 96) ≈ **2.3 KB**, plus name entries 24 × (align4(5)+8 = 16) ≈ **0.4 KB** → **~2.7 KB total live**, a small slice of the ~23–25 KB free.
- **Write discipline:** accumulate records into the current page in a small RAM shadow; persist the page to its key only when (a) the page fills, or (b) a **critical event** — deep-sleep entry (the synchronous `activity_state_changed→SLEEP` flush hook from §3.2 guarantees the page lands before `sys_poweroff`) or a charging-state change. The monotonic page-sequence header lets readback order pages and locate oldest/newest after a reboot.
- **Wear:** with flush-on-fill + critical-events, writes are on the order of **tens per day** → flash easily lasts decades (nRF52840 ≈ 10 k erase/page). A naive *persist-every-transition* scheme (~96 B × ~300/day) would instead fill ~1 sector/day and erode endurance in a few years — **avoid it**; the page batching is what makes NVS viable here.

**Cheaper alternative if a full event log isn't needed:** keep only fixed aggregate counters (`cum_active_ms`, `cum_idle_ms`, `cum_sleep_ms`, `cum_charging_ms`, session histogram buckets) in a handful of keys — a few hundred bytes, a couple of writes per sleep, near-zero wear. This still answers "awake too long vs. matched use," just without the per-segment timeline.

Net: the log fits comfortably in NVS. The wins come from **compact 2-byte records + short keys + page-batched writes flushed on fill/critical events**, which keep both the footprint (~3 KB) and the flash wear (tens of writes/day) tiny.

## 3d. Implementation status (2026-06-26)

Built and flashed to both halves, verified live over the debug RPC:

- **`nvsfree`** ([src/debug_rpc.c](../src/debug_rpc.c)) — measured **free 25,720 B used 2,896 B** on the central, **free 27,572 B used 1,044 B** on the peripheral, of a 28,616 B usable ceiling (`(8−1)×(4096−8)`). Confirms §3c's estimate; ample room for the log.
- **Page-ring log** ([src/toucan_sleep_log.c](../src/toucan_sleep_log.c), [include/toucan/sleep_log.h](../include/toucan/sleep_log.h), `CONFIG_TOUCAN_SLEEP_LOG`) — 2-byte records, 32 pages × 42 records as `tsl/<n>` keys, flush on page-fill / sleep-entry / charging-change, hourly checkpoint, boot-resume of the newest partial page.
- **`sleeplog` RPC** — indexed one-page-per-request (`sleeplog` → `slots`/`cur`; `sleeplog <i>` → one `OK` line with hex records), because the firmware RPC transport / `toucan_debug.RPCSession` only returns the single terminating `OK`/`ERR` line. Read back with `toucan_debug.RPCSession(side).request(...)`.

First live records decoded correctly: a 30 s ACTIVE segment (the `CONFIG_ZMK_IDLE_TIMEOUT`) on both halves.

### ⚠️ Finding: charging is not detected on the peripheral

The central logged `chg=1`, the peripheral `chg=0` — **while both were physically on USB.** `zmk_usb_is_powered()` / `zmk_usb_conn_state_changed` report "not powered" on the peripheral (it never enumerates a USB *connection* the way the central does). So the log's charging bit is only trustworthy on the central. To track charge state on the right half we'd need a different signal — a VBUS/charge-detect GPIO or the battery charger status — not the USB connection state. Until then, treat the peripheral's `chg` as "unknown / always 0".

## 4. Suggested next actions

1. **Confirm** with the rapid-sleep + DBG-log technique in §2 (cheap, no new code).
2. ~~Fix the misleading SOFT_OFF comment~~ — **done** (both `.conf` files updated 2026-06-26).
3. ~~Measure true NVS free space~~ — **done** via the `nvsfree` RPC (§3d).
4. ~~Implement the NVS page-ring log~~ — **done** (§3d); still open: aggregate `sleepstats` counters per §3, and a proper persistence-across-deep-sleep soak test (records only reach NVS on flush events, not yet force-tested this session).
5. **Fix peripheral charging detection** (§3d) before relying on right-half `chg` data.
6. Interpret per §3.4; if noise-driven, evaluate `CONFIG_ZMK_INPUT_PINNACLE_IDLE_SLEEPER` (currently off by deliberate UX choice, [toucan_right.conf](../boards/shields/toucan/toucan_right.conf)).
