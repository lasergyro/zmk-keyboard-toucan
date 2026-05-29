/*
 * Copyright (c) 2025 The ZMK Contributors
 *
 * SPDX-License-Identifier: MIT
 */

#if defined(CONFIG_SHIELD_TOUCAN_RIGHT)

#define DT_DRV_COMPAT zmk_behavior_debug_inject

#include <zephyr/device.h>
#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

// Forward declaration to access the gesture injection hook in the Cirque driver
void cirque_pinnacle_inject_abs(const struct device *dev, int16_t x, int16_t y, int8_t z);

static int on_keymap_binding_pressed(struct zmk_behavior_binding *binding,
                                     struct zmk_behavior_binding_event event) {
    int16_t x = binding->param1 & 0xFFFF;
    int16_t y = (binding->param1 >> 16) & 0xFFFF;
    int8_t z = binding->param2 & 0xFF;

    LOG_DBG("Injecting ABS event to cirque: x=%d y=%d z=%d", x, y, z);

    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(glidepoint));
    if (device_is_ready(dev)) {
        cirque_pinnacle_inject_abs(dev, x, y, z);
    } else {
        LOG_WRN("Cirque device not ready for debug injection");
    }

    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_keymap_binding_released(struct zmk_behavior_binding *binding,
                                      struct zmk_behavior_binding_event event) {
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api behavior_debug_inject_driver_api = {
    .binding_pressed = on_keymap_binding_pressed,
    .binding_released = on_keymap_binding_released,
};

static int behavior_debug_inject_init(const struct device *dev) {
    LOG_INF("behavior_debug_inject_init called for device: %s", dev->name);
    
    STRUCT_SECTION_FOREACH(zmk_behavior_ref, item) {
        LOG_INF("Found behavior ref: %s (ready: %d)", item->device->name, z_device_is_ready(item->device));
    }
    
    return 0;
}

#define DBG_INJ_INST(n) \
    BEHAVIOR_DT_INST_DEFINE(n, behavior_debug_inject_init, NULL, NULL, NULL, POST_KERNEL, \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &behavior_debug_inject_driver_api);

DT_INST_FOREACH_STATUS_OKAY(DBG_INJ_INST)

#endif // CONFIG_SHIELD_TOUCAN_RIGHT
