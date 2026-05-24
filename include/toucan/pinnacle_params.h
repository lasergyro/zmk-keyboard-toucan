#pragma once

/* Public API for runtime gesture parameter access on the Cirque Pinnacle.
 * The driver (input_pinnacle.c) exposes these; debug_rpc.c calls them. */

#include <stdint.h>
#include <zephyr/device.h>

/* Read a gesture param by its C field name (e.g. "tap_timeout_ms").
 * Returns 0 on success, -EINVAL for unknown key. */
int pinnacle_gesture_param_get(const struct device *dev, const char *key, int32_t *out);

/* Write a gesture param by its C field name.  Takes effect immediately in
 * the running driver.  Does NOT persist — callers that want persistence
 * (debug_rpc.c) must call settings_save_one themselves.
 * Returns 0 on success, -EINVAL for unknown key. */
int pinnacle_gesture_param_set(const struct device *dev, const char *key, int32_t value);
