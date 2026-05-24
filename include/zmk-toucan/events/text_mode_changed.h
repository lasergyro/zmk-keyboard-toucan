#pragma once

#include <zephyr/kernel.h>
#include <zmk/event_manager.h>

struct zmk_toucan_text_mode_changed {
    uint8_t host_mode;
    int64_t timestamp;
};

ZMK_EVENT_DECLARE(zmk_toucan_text_mode_changed);

static inline int raise_toucan_text_mode_changed(uint8_t host_mode) {
    return raise_zmk_toucan_text_mode_changed((struct zmk_toucan_text_mode_changed){
        .host_mode = host_mode,
        .timestamp = k_uptime_get(),
    });
}
