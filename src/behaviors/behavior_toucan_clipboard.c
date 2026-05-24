#define DT_DRV_COMPAT zmk_behavior_toucan_clipboard

#include <drivers/behavior.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>

#include <zmk/behavior.h>
#include <zmk/behavior_queue.h>

#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk-toucan/text.h>

#include <zmk-toucan/text_state.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#ifdef DT_N_NODELABEL_kp
#define TOUCAN_KEY_PRESS_BEHAVIOR_DEV DEVICE_DT_NAME(DT_NODELABEL(kp))
#else
#define TOUCAN_KEY_PRESS_BEHAVIOR_DEV "key_press"
#endif

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

static zmk_key_t clipboard_keycode(uint32_t action) {
    bool use_gui = toucan_text_mode_get_current() != TOUCAN_TEXT_MODE_LINUX;

    switch (action) {
    case TOUCAN_CLIPBOARD_CUT:
        return use_gui ? LG(X) : LC(X);
    case TOUCAN_CLIPBOARD_COPY:
        return use_gui ? LG(C) : LC(C);
    case TOUCAN_CLIPBOARD_PASTE:
        return use_gui ? LG(V) : LC(V);
    default:
        return 0;
    }
}

static int on_clipboard_pressed(struct zmk_behavior_binding *binding,
                                struct zmk_behavior_binding_event event) {
    zmk_key_t key = clipboard_keycode(binding->param1);
    if (key == 0) {
        LOG_ERR("Unknown clipboard action: %u", binding->param1);
        return -EINVAL;
    }

    LOG_DBG("clipboard action=%u key=0x%x", binding->param1, key);

    struct zmk_behavior_binding b = {
        .behavior_dev = TOUCAN_KEY_PRESS_BEHAVIOR_DEV,
        .param1 = key,
    };
    zmk_behavior_queue_add(&event, b, true, 5);
    zmk_behavior_queue_add(&event, b, false, 0);

    return 0;
}

static int on_clipboard_released(struct zmk_behavior_binding *binding,
                                 struct zmk_behavior_binding_event event) {
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api behavior_toucan_clipboard_driver_api = {
    .binding_pressed = on_clipboard_pressed,
    .binding_released = on_clipboard_released,
};

BEHAVIOR_DT_INST_DEFINE(0, NULL, NULL, NULL, NULL, POST_KERNEL,
                        CONFIG_KERNEL_INIT_PRIORITY_DEFAULT,
                        &behavior_toucan_clipboard_driver_api);

#endif /* DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT) */
