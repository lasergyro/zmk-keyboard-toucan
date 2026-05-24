#define DT_DRV_COMPAT zmk_behavior_toucan_output_mode

#include <drivers/behavior.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>

#include <zmk/behavior.h>

#include <dt-bindings/zmk-toucan/text.h>

#include <zmk-toucan/text_state.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

static const char *output_action_name(uint32_t action) {
    switch (action) {
    case TOUCAN_TEXT_ACTION_SET_LINUX:
        return "set-linux";
    case TOUCAN_TEXT_ACTION_SET_MACOS:
        return "set-macos";
    case TOUCAN_TEXT_ACTION_SET_IOS:
        return "set-ios";
    case TOUCAN_TEXT_ACTION_CYCLE_HOST_MODE:
        return "cycle-host-mode";
    case TOUCAN_TEXT_ACTION_TOGGLE_GREEK_MODE:
        return "toggle-greek-mode";
    default:
        return "unknown";
    }
}

static int on_output_mode_pressed(struct zmk_behavior_binding *binding,
                                  struct zmk_behavior_binding_event event) {
    LOG_DBG("hostmode action=%s (%u)", output_action_name(binding->param1), binding->param1);

    switch (binding->param1) {
    case TOUCAN_TEXT_ACTION_SET_LINUX:
        return toucan_text_mode_set_current(TOUCAN_TEXT_MODE_LINUX);
    case TOUCAN_TEXT_ACTION_SET_MACOS:
        return toucan_text_mode_set_current(TOUCAN_TEXT_MODE_MACOS);
    case TOUCAN_TEXT_ACTION_SET_IOS:
        return toucan_text_mode_set_current(TOUCAN_TEXT_MODE_IOS);
    case TOUCAN_TEXT_ACTION_CYCLE_HOST_MODE:
        return toucan_text_mode_cycle_current();
    case TOUCAN_TEXT_ACTION_TOGGLE_GREEK_MODE:
        return toucan_text_greek_mode_toggle_current();
    default:
        LOG_ERR("Unknown Toucan output action: %u", binding->param1);
        return -EINVAL;
    }
}

static int on_output_mode_released(struct zmk_behavior_binding *binding,
                                   struct zmk_behavior_binding_event event) {
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api behavior_toucan_output_mode_driver_api = {
    .binding_pressed = on_output_mode_pressed,
    .binding_released = on_output_mode_released,
};

BEHAVIOR_DT_INST_DEFINE(0, NULL, NULL, NULL, NULL, POST_KERNEL,
                        CONFIG_KERNEL_INIT_PRIORITY_DEFAULT,
                        &behavior_toucan_output_mode_driver_api);

#endif /* DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT) */
