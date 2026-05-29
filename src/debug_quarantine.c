/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: MIT
 */

#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

#include <dt-bindings/zmk/hid_usage_pages.h>
#include <zmk/endpoints.h>
#include <zmk/hid.h>

#include <toucan/debug_quarantine.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

static bool quarantine_enabled = false;

int __real_zmk_endpoints_send_report(uint16_t usage_page);
int __real_zmk_endpoints_send_mouse_report(void);

extern void toucan_debug_rpc_capture_hid_report(uint16_t usage_page);
extern void toucan_debug_rpc_capture_mouse_report(void);

bool toucan_debug_quarantine_is_enabled(void) { return quarantine_enabled; }

static void quarantine_clear_reports_if_supported(void) {
#if !IS_ENABLED(CONFIG_ZMK_SPLIT) || IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
    zmk_endpoints_clear_current();
#endif
}

int toucan_debug_quarantine_set_enabled(bool enabled) {
    if (enabled == quarantine_enabled) {
        return 0;
    }

    if (enabled) {
        quarantine_enabled = false;
        quarantine_clear_reports_if_supported();
        quarantine_enabled = true;
    } else {
        quarantine_clear_reports_if_supported();
        quarantine_enabled = false;
    }

    LOG_WRN("Debug quarantine %s", enabled ? "enabled" : "disabled");
    return 0;
}

int __wrap_zmk_endpoints_send_report(uint16_t usage_page) {
    toucan_debug_rpc_capture_hid_report(usage_page);

    if (quarantine_enabled) {
        LOG_INF("Debug quarantine dropped HID report usage page 0x%02X", usage_page);
        return 0;
    }

    return __real_zmk_endpoints_send_report(usage_page);
}

int __wrap_zmk_endpoints_send_mouse_report(void) {
    toucan_debug_rpc_capture_mouse_report();

    if (quarantine_enabled) {
        const struct zmk_hid_mouse_report_body *report = &zmk_hid_get_mouse_report()->body;
        LOG_INF(
            "Debug quarantine dropped mouse report buttons=0x%02X move=%d/%d scroll=%d/%d",
            report->buttons, report->d_x, report->d_y, report->d_scroll_x,
            report->d_scroll_y);
        return 0;
    }

    return __real_zmk_endpoints_send_mouse_report();
}
