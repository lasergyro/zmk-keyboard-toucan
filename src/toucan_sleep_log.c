/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: MIT
 *
 * Persistent rotating log of per-half activity (active/idle) and charging
 * durations. Each state segment is recorded as a 2-byte entry; entries are
 * batched into fixed pages and stored as a ring of short `tsl/<n>` settings
 * keys in NVS, so the history survives deep sleep (System OFF wipes RAM).
 *
 * Flush policy (keeps flash wear to tens of writes/day):
 *   - page fills (42 records),
 *   - deep-sleep entry (synchronous, lands before sys_poweroff),
 *   - charging-state change (rare).
 * An hourly checkpoint closes+reopens the open segment so long idle/charging
 * spans don't saturate the 13-bit (≈2.27 h) duration field.
 *
 * See plans/2026-06-26-right-half-sleep-investigation.md (§3c).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/init.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>

#include <zmk/activity.h>
#include <zmk/event_manager.h>
#include <zmk/events/activity_state_changed.h>

/* Charging ("on USB power") is read straight from the nRF VBUS comparator. ZMK's
 * zmk_usb_is_powered() tracks the USB *device* connection state, which is only
 * updated for the HID device on the central — on the peripheral it stays NONE
 * even while plugged in. The VBUS register is independent of USB role and works
 * on both halves. */
#if IS_ENABLED(CONFIG_NRFX_POWER)
#include <hal/nrf_power.h>
#endif
#if IS_ENABLED(CONFIG_ZMK_USB)
#include <zmk/usb.h>
#include <zmk/events/usb_conn_state_changed.h>
#endif

#include <toucan/sleep_log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#define SL_NUM_PAGES   TOUCAN_SLEEP_LOG_NUM_PAGES
#define SL_CHECKPOINT_S 3600 /* hourly: cap open segments + commit to NVS */
#define SL_STATE_SLEEP 2     /* matches ZMK_ACTIVITY_SLEEP */

BUILD_ASSERT(sizeof(struct toucan_sleep_log_page) == 88, "unexpected page size");

static K_MUTEX_DEFINE(sl_lock);

/* Current (open) page shadow and where it lives in the ring. */
static struct toucan_sleep_log_page cur;
static uint8_t cur_slot;
static uint16_t next_seq;

/* Open segment being timed. */
static uint8_t cur_state;
static bool cur_charging;
static int64_t seg_start;
static bool initialized;

/* Boot-scan: newest page found while settings load, used to resume/rotate. */
static struct toucan_sleep_log_page boot_newest;
static int boot_newest_slot = -1;

static inline bool seq_after(uint16_t a, uint16_t b) { return (int16_t)(a - b) > 0; }

static inline bool sl_charging_now(void) {
#if IS_ENABLED(CONFIG_NRFX_POWER)
    return nrf_power_usbregstatus_vbusdet_get(NRF_POWER);
#elif IS_ENABLED(CONFIG_ZMK_USB)
    return zmk_usb_is_powered();
#else
    return false;
#endif
}

static inline uint16_t sl_encode(uint8_t state, bool chg, uint32_t dur_s) {
    if (dur_s > TOUCAN_SLEEP_LOG_MAX_DUR_S) {
        dur_s = TOUCAN_SLEEP_LOG_MAX_DUR_S;
    }
    return (uint16_t)((dur_s << TOUCAN_SLEEP_LOG_DUR_SHIFT) |
                      (chg ? TOUCAN_SLEEP_LOG_CHG_BIT : 0) |
                      (state & TOUCAN_SLEEP_LOG_STATE_MASK));
}

/* --- helpers below assume sl_lock is held --- */

static void sl_flush_locked(void) {
#if IS_ENABLED(CONFIG_SETTINGS)
    char path[16];
    snprintf(path, sizeof(path), "tsl/%u", cur_slot);
    int rc = settings_save_one(path, &cur, sizeof(cur));
    if (rc) {
        LOG_WRN("sleeplog: save %s failed %d", path, rc);
    }
#endif
}

static void sl_append_locked(uint16_t rec) {
    cur.rec[cur.count++] = rec;
    if (cur.count >= TOUCAN_SLEEP_LOG_PAGE_RECORDS) {
        sl_flush_locked();
        /* Rotate to the next ring slot with a fresh sequence number. */
        cur_slot = (uint8_t)((cur_slot + 1) % SL_NUM_PAGES);
        memset(&cur, 0, sizeof(cur));
        cur.seq = next_seq++;
    }
}

/* Record the elapsed time of the open segment, then switch to (ns, nc). */
static void sl_close_segment_locked(uint8_t ns, bool nc) {
    int64_t now = k_uptime_get();
    uint32_t dur_s = (uint32_t)((now - seg_start) / 1000);
    sl_append_locked(sl_encode(cur_state, cur_charging, dur_s));
    cur_state = ns;
    cur_charging = nc;
    seg_start = now;
}

/* --- event-driven entry points --- */

static int sl_activity_listener(const zmk_event_t *eh) {
    const struct zmk_activity_state_changed *ev = as_zmk_activity_state_changed(eh);
    if (!ev || !initialized) {
        return 0;
    }

    bool chg = sl_charging_now(); /* fold in any charging change for free */
    k_mutex_lock(&sl_lock, K_FOREVER);
    if ((uint8_t)ev->state == SL_STATE_SLEEP) {
        /* Entering deep sleep: record the segment that ended, drop a SLEEP
         * marker, and flush synchronously before the kernel powers off. */
        sl_close_segment_locked(SL_STATE_SLEEP, chg);
        sl_append_locked(sl_encode(SL_STATE_SLEEP, chg, 0));
        sl_flush_locked();
    } else {
        sl_close_segment_locked((uint8_t)ev->state, chg);
    }
    k_mutex_unlock(&sl_lock);
    return 0;
}

ZMK_LISTENER(toucan_sleep_log_activity, sl_activity_listener);
ZMK_SUBSCRIPTION(toucan_sleep_log_activity, zmk_activity_state_changed);

#if IS_ENABLED(CONFIG_ZMK_USB)
/* Event-driven charging change (accurate on the central). Re-reads VBUS rather
 * than trusting the event's conn_state so it agrees with sl_charging_now(). */
static int sl_usb_listener(const zmk_event_t *eh) {
    if (!as_zmk_usb_conn_state_changed(eh) || !initialized) {
        return 0;
    }
    bool chg = sl_charging_now();
    k_mutex_lock(&sl_lock, K_FOREVER);
    if (chg != cur_charging) {
        sl_close_segment_locked(cur_state, chg);
        sl_flush_locked();
    }
    k_mutex_unlock(&sl_lock);
    return 0;
}

ZMK_LISTENER(toucan_sleep_log_usb, sl_usb_listener);
ZMK_SUBSCRIPTION(toucan_sleep_log_usb, zmk_usb_conn_state_changed);
#endif

/* Hourly checkpoint. This is the ONLY periodic timer in the module, and it is
 * deliberately coarse: it raises no input/activity events, so it never resets
 * ZMK's idle/sleep timer or blocks deep sleep, and during deep sleep (System
 * OFF) it is powered down and cannot wake the device. Once an hour it splits the
 * open segment (so its duration can't saturate the 13-bit field), folds in any
 * charging change the event listeners missed (e.g. plugging in while idle and
 * untouched), and commits to NVS so an unexpected power-off (manual off / battery
 * pull — which the device can't time) loses at most ~1 h. */
static void sl_checkpoint_work_cb(struct k_work *work) {
    ARG_UNUSED(work);
    if (!initialized) {
        return;
    }
    bool chg = sl_charging_now();
    k_mutex_lock(&sl_lock, K_FOREVER);
    sl_close_segment_locked(cur_state, chg);
    sl_flush_locked();
    k_mutex_unlock(&sl_lock);
}

static K_WORK_DEFINE(sl_checkpoint_work, sl_checkpoint_work_cb);

static void sl_checkpoint_timer_cb(struct k_timer *timer) {
    ARG_UNUSED(timer);
    k_work_submit(&sl_checkpoint_work);
}

static K_TIMER_DEFINE(sl_checkpoint_timer, sl_checkpoint_timer_cb, NULL);

/* --- settings load / init --- */

static int sl_settings_set(const char *name, size_t len, settings_read_cb read_cb, void *cb_arg) {
    char *endptr = NULL;
    long slot = strtol(name, &endptr, 10);
    if (name[0] == '\0' || !endptr || *endptr != '\0' || slot < 0 || slot >= SL_NUM_PAGES) {
        return -EINVAL;
    }
    if (len != sizeof(struct toucan_sleep_log_page)) {
        return -EINVAL;
    }

    struct toucan_sleep_log_page page;
    int err = read_cb(cb_arg, &page, sizeof(page));
    if (err <= 0) {
        return err;
    }

    if (boot_newest_slot < 0 || seq_after(page.seq, boot_newest.seq)) {
        boot_newest = page;
        boot_newest_slot = (int)slot;
    }
    return 0;
}

static int sl_settings_commit(void) {
    k_mutex_lock(&sl_lock, K_FOREVER);
    if (boot_newest_slot >= 0 && boot_newest.count < TOUCAN_SLEEP_LOG_PAGE_RECORDS) {
        /* Resume the newest partial page so we don't waste a ring slot per boot. */
        cur = boot_newest;
        cur_slot = (uint8_t)boot_newest_slot;
        next_seq = boot_newest.seq + 1;
    } else if (boot_newest_slot >= 0) {
        /* Newest page is full: start fresh in the next slot. */
        cur_slot = (uint8_t)((boot_newest_slot + 1) % SL_NUM_PAGES);
        memset(&cur, 0, sizeof(cur));
        cur.seq = boot_newest.seq + 1;
        next_seq = cur.seq + 1;
    } else {
        /* Fresh device, nothing stored yet. */
        cur_slot = 0;
        memset(&cur, 0, sizeof(cur));
        cur.seq = 0;
        next_seq = 1;
    }

    cur_state = (uint8_t)zmk_activity_get_state();
    cur_charging = sl_charging_now();
    seg_start = k_uptime_get();
    initialized = true;
    k_mutex_unlock(&sl_lock);

    k_timer_start(&sl_checkpoint_timer, K_SECONDS(SL_CHECKPOINT_S), K_SECONDS(SL_CHECKPOINT_S));
    LOG_INF("sleeplog: ready slot=%u seq=%u state=%u charging=%d", cur_slot, cur.seq, cur_state,
            cur_charging);
    return 0;
}

SETTINGS_STATIC_HANDLER_DEFINE(toucan_sleep_log, "tsl", NULL, sl_settings_set, sl_settings_commit,
                               NULL);

/* --- read-out for the debug RPC dump (one page per request) --- */

uint8_t toucan_sleep_log_cur_slot(void) { return cur_slot; }

int toucan_sleep_log_flush(void) {
    if (!initialized) {
        return -EAGAIN;
    }
    k_mutex_lock(&sl_lock, K_FOREVER);
    if ((k_uptime_get() - seg_start) >= MSEC_PER_SEC) {
        sl_close_segment_locked(cur_state, cur_charging);
    }
    sl_flush_locked();
    k_mutex_unlock(&sl_lock);
    return 0;
}

struct sl_getp_ctx {
    uint8_t target;
    struct toucan_sleep_log_page *out;
    bool found;
};

static int sl_getp_cb(const char *key, size_t len, settings_read_cb read_cb, void *cb_arg,
                      void *param) {
    struct sl_getp_ctx *g = param;

    char *endptr = NULL;
    long slot = strtol(key, &endptr, 10);
    if (key[0] == '\0' || !endptr || *endptr != '\0' || (uint8_t)slot != g->target) {
        return 0;
    }
    if (len != sizeof(struct toucan_sleep_log_page)) {
        return 0;
    }
    if (read_cb(cb_arg, g->out, sizeof(*g->out)) > 0) {
        g->found = true;
    }
    return 0;
}

bool toucan_sleep_log_get_page(uint8_t slot, struct toucan_sleep_log_page *out) {
    if (!initialized || slot >= SL_NUM_PAGES) {
        return false;
    }

    k_mutex_lock(&sl_lock, K_FOREVER);
    if (slot == cur_slot) {
        *out = cur;
        k_mutex_unlock(&sl_lock);
        return true;
    }
    k_mutex_unlock(&sl_lock);

#if IS_ENABLED(CONFIG_SETTINGS)
    struct sl_getp_ctx g = {.target = slot, .out = out, .found = false};
    settings_load_subtree_direct("tsl", sl_getp_cb, &g);
    return g.found;
#else
    return false;
#endif
}
