/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: MIT
 */

#include <zephyr/logging/log.h>

#include <zmk/event_manager.h>
#include <zmk/events/layer_state_changed.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#define TOUCAN_PAD_LAYER 3

static int toucan_debug_pad_trace_listener(const zmk_event_t *eh) {
    const struct zmk_layer_state_changed *layer_ev = as_zmk_layer_state_changed(eh);
    if (layer_ev != NULL && layer_ev->layer == TOUCAN_PAD_LAYER) {
        LOG_INF("PAD layer %s", layer_ev->state ? "on" : "off");
    }

    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(toucan_debug_pad_trace, toucan_debug_pad_trace_listener);
ZMK_SUBSCRIPTION(toucan_debug_pad_trace, zmk_layer_state_changed);
