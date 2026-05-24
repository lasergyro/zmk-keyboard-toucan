/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: MIT
 */

#include <errno.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/dt-bindings/input/input-event-codes.h>
#include <zephyr/input/input.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/init.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>
#include <zephyr/sys/reboot.h>

#include <toucan/pinnacle_params.h>

#include <dt-bindings/zmk/reset.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/split/peripheral.h>

#include <toucan/debug_quarantine.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#if !DT_HAS_CHOSEN(zmk_toucan_debug_rpc_uart)
#error "CONFIG_TOUCAN_DEBUG_RPC requires zmk,toucan-debug-rpc-uart chosen (set in toucan_left_debug.overlay)"
#endif

#if defined(CONFIG_SHIELD_TOUCAN_LEFT)
#define TOUCAN_DEBUG_RPC_SIDE "left"
#elif defined(CONFIG_SHIELD_TOUCAN_RIGHT)
#define TOUCAN_DEBUG_RPC_SIDE "right"
#else
#define TOUCAN_DEBUG_RPC_SIDE "unknown"
#endif

#if defined(CONFIG_ZMK_SPLIT) && defined(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
#define TOUCAN_DEBUG_RPC_ROLE "central"
#elif defined(CONFIG_ZMK_SPLIT)
#define TOUCAN_DEBUG_RPC_ROLE "peripheral"
#else
#define TOUCAN_DEBUG_RPC_ROLE "standalone"
#endif

#define TOUCAN_DEBUG_RPC_UART_NODE DT_CHOSEN(zmk_toucan_debug_rpc_uart)
#define TOUCAN_DEBUG_RPC_CMD_MAX_LEN 80
#define TOUCAN_DEBUG_RPC_QUEUE_LEN 4
#define TOUCAN_DEBUG_RPC_STACK_SIZE 2048

#if defined(CONFIG_SHIELD_TOUCAN_RIGHT)
#define TOUCAN_DEBUG_TOUCH_DEVICE_NODE DT_NODELABEL(glidepoint)
#elif defined(CONFIG_SHIELD_TOUCAN_LEFT)
#define TOUCAN_DEBUG_TOUCH_DEVICE_NODE DT_NODELABEL(glidepoint_split)
#endif

struct toucan_debug_rpc_cmd {
    char text[TOUCAN_DEBUG_RPC_CMD_MAX_LEN];
};

static const struct device *const debug_rpc_uart = DEVICE_DT_GET(TOUCAN_DEBUG_RPC_UART_NODE);
#if defined(TOUCAN_DEBUG_TOUCH_DEVICE_NODE)
static const struct device *const touch_inject_device =
    DEVICE_DT_GET(TOUCAN_DEBUG_TOUCH_DEVICE_NODE);
#endif

K_MSGQ_DEFINE(toucan_debug_rpc_cmdq, sizeof(struct toucan_debug_rpc_cmd),
              TOUCAN_DEBUG_RPC_QUEUE_LEN, 1);
K_THREAD_STACK_DEFINE(toucan_debug_rpc_stack, TOUCAN_DEBUG_RPC_STACK_SIZE);
static struct k_thread toucan_debug_rpc_thread;

static char rx_line[TOUCAN_DEBUG_RPC_CMD_MAX_LEN];
static size_t rx_len;
static bool rx_overflow;

static void uart_write_str(const char *text) {
    LOG_INF("Debug RPC reply: %s", text);

    for (const char *p = text; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }

    uart_poll_out(debug_rpc_uart, '\r');
    uart_poll_out(debug_rpc_uart, '\n');
}

static void uart_write_identity(const char *prefix) {
    LOG_INF("Debug RPC reply: %s side=%s role=%s quarantine=%s", prefix, TOUCAN_DEBUG_RPC_SIDE,
            TOUCAN_DEBUG_RPC_ROLE, toucan_debug_quarantine_is_enabled() ? "on" : "off");

    for (const char *p = prefix; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }

    uart_poll_out(debug_rpc_uart, ' ');

    const char *side_prefix = "side=";
    for (const char *p = side_prefix; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }
    for (const char *p = TOUCAN_DEBUG_RPC_SIDE; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }

    uart_poll_out(debug_rpc_uart, ' ');

    const char *role_prefix = "role=";
    for (const char *p = role_prefix; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }
    for (const char *p = TOUCAN_DEBUG_RPC_ROLE; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }

    uart_poll_out(debug_rpc_uart, ' ');

    const char *quarantine_prefix = "quarantine=";
    for (const char *p = quarantine_prefix; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }
    const char *quarantine_state = toucan_debug_quarantine_is_enabled() ? "on" : "off";
    for (const char *p = quarantine_state; *p; p++) {
        uart_poll_out(debug_rpc_uart, *p);
    }

    uart_poll_out(debug_rpc_uart, '\r');
    uart_poll_out(debug_rpc_uart, '\n');
}

static int parse_long_arg(const char *text, long *value) {
    if (!text || !value) {
        return -EINVAL;
    }

    errno = 0;
    char *end = NULL;
    long parsed = strtol(text, &end, 10);

    if (errno != 0 || end == text || *end != '\0') {
        return -EINVAL;
    }

    *value = parsed;
    return 0;
}

static int parse_pressed_arg(const char *text, bool *pressed) {
    if (!text || !pressed) {
        return -EINVAL;
    }

    if (strcmp(text, "down") == 0 || strcmp(text, "press") == 0 || strcmp(text, "on") == 0 ||
        strcmp(text, "1") == 0) {
        *pressed = true;
        return 0;
    }

    if (strcmp(text, "up") == 0 || strcmp(text, "release") == 0 || strcmp(text, "off") == 0 ||
        strcmp(text, "0") == 0) {
        *pressed = false;
        return 0;
    }

    return -EINVAL;
}

static int inject_key_position(uint32_t position, bool pressed) {
    LOG_INF("Injected debug key event: position=%u state=%s", position,
            pressed ? "down" : "up");
    return raise_zmk_position_state_changed((struct zmk_position_state_changed){
        .source = ZMK_POSITION_STATE_CHANGE_SOURCE_LOCAL,
        .position = position,
        .state = pressed,
        .timestamp = k_uptime_get(),
    });
}

static int inject_touch_state(bool pressed) {
#if defined(TOUCAN_DEBUG_TOUCH_DEVICE_NODE)
    if (!device_is_ready(touch_inject_device)) {
        return -ENODEV;
    }

    LOG_INF("Injected debug touch event: state=%s", pressed ? "down" : "up");

    return input_report_key(touch_inject_device, INPUT_BTN_TOUCH, pressed ? 1 : 0, true,
                            K_FOREVER);
#else
    ARG_UNUSED(pressed);
    return -ENOTSUP;
#endif
}

static int inject_touch_abs(int32_t x, int32_t y) {
#if defined(TOUCAN_DEBUG_TOUCH_DEVICE_NODE)
    if (!device_is_ready(touch_inject_device)) {
        return -ENODEV;
    }

    LOG_INF("Injected debug abs event: x=%d y=%d", x, y);

    int ret = input_report_abs(touch_inject_device, INPUT_ABS_X, x, false, K_FOREVER);
    if (ret < 0) {
        return ret;
    }

    return input_report_abs(touch_inject_device, INPUT_ABS_Y, y, true, K_FOREVER);
#else
    ARG_UNUSED(x);
    ARG_UNUSED(y);
    return -ENOTSUP;
#endif
}

static int inject_touch_move(int32_t dx, int32_t dy) {
#if defined(TOUCAN_DEBUG_TOUCH_DEVICE_NODE)
    if (!device_is_ready(touch_inject_device)) {
        return -ENODEV;
    }

    if (dx == 0 && dy == 0) {
        return 0;
    }

    LOG_INF("Injected debug move event: dx=%d dy=%d", dx, dy);

    int ret = 0;

    if (dx != 0) {
        ret = input_report_rel(touch_inject_device, INPUT_REL_X, dx, dy == 0, K_FOREVER);
        if (ret < 0) {
            return ret;
        }
    }

    if (dy != 0) {
        ret = input_report_rel(touch_inject_device, INPUT_REL_Y, dy, true, K_FOREVER);
    }

    return ret;
#else
    ARG_UNUSED(dx);
    ARG_UNUSED(dy);
    return -ENOTSUP;
#endif
}

static void queue_line(void) {
    struct toucan_debug_rpc_cmd cmd = {0};

    if (rx_len == 0) {
        return;
    }

    for (size_t i = 0; i < rx_len; i++) {
        cmd.text[i] = rx_line[i];
    }
    cmd.text[rx_len] = '\0';

    if (k_msgq_put(&toucan_debug_rpc_cmdq, &cmd, K_NO_WAIT) != 0) {
        LOG_WRN("Dropping debug RPC command, queue full");
    }
}

static void uart_cb(const struct device *dev, void *user_data) {
    ARG_UNUSED(dev);
    ARG_UNUSED(user_data);

    if (!uart_irq_update(debug_rpc_uart) || !uart_irq_rx_ready(debug_rpc_uart)) {
        return;
    }

    uint8_t buf[16];
    int read_len;

    while ((read_len = uart_fifo_read(debug_rpc_uart, buf, sizeof(buf))) > 0) {
        for (int i = 0; i < read_len; i++) {
            uint8_t c = buf[i];

            if (c == '\r') {
                continue;
            }

            if (c == '\n') {
                if (!rx_overflow) {
                    queue_line();
                }
                rx_len = 0;
                rx_overflow = false;
                continue;
            }

            if (c < 0x20 || c > 0x7e) {
                continue;
            }

            if (rx_len >= (TOUCAN_DEBUG_RPC_CMD_MAX_LEN - 1)) {
                rx_overflow = true;
                continue;
            }

            rx_line[rx_len++] = (char)c;
        }
    }
}

static void reset_after_reply(void) {
    uart_write_str("OK reset");
    k_sleep(K_MSEC(50));
    sys_reboot(SYS_REBOOT_COLD);
}

static void bootloader_after_reply(void) {
    uart_write_str("OK bootloader");
    k_sleep(K_MSEC(50));
    sys_reboot(RST_UF2);
}

static void process_key_command(char *args) {
    char *saveptr = NULL;
    char *position_text = strtok_r(args, " ", &saveptr);
    char *state_text = strtok_r(NULL, " ", &saveptr);

    if (!position_text || !state_text || strtok_r(NULL, " ", &saveptr)) {
        uart_write_str("ERR usage: key <position> <down|up>");
        return;
    }

    long position = 0;
    bool pressed = false;

    if (parse_long_arg(position_text, &position) < 0 || position < 0 ||
        parse_pressed_arg(state_text, &pressed) < 0) {
        uart_write_str("ERR invalid key arguments");
        return;
    }

    int ret = inject_key_position((uint32_t)position, pressed);
    if (ret < 0) {
        uart_write_str("ERR key inject failed");
        return;
    }

    uart_write_str(pressed ? "OK key down" : "OK key up");
}

static void process_tap_command(char *args) {
    char *saveptr = NULL;
    char *position_text = strtok_r(args, " ", &saveptr);

    if (!position_text || strtok_r(NULL, " ", &saveptr)) {
        uart_write_str("ERR usage: tap <position>");
        return;
    }

    long position = 0;
    if (parse_long_arg(position_text, &position) < 0 || position < 0) {
        uart_write_str("ERR invalid tap position");
        return;
    }

    int ret = inject_key_position((uint32_t)position, true);
    if (ret < 0) {
        uart_write_str("ERR tap down failed");
        return;
    }

    k_sleep(K_MSEC(5));

    ret = inject_key_position((uint32_t)position, false);
    if (ret < 0) {
        uart_write_str("ERR tap up failed");
        return;
    }

    uart_write_str("OK tap");
}

static void process_touch_command(char *args) {
    char *saveptr = NULL;
    char *state_text = strtok_r(args, " ", &saveptr);
    bool pressed = false;

    if (!state_text || strtok_r(NULL, " ", &saveptr) ||
        parse_pressed_arg(state_text, &pressed) < 0) {
        uart_write_str("ERR usage: touch <down|up>");
        return;
    }

    int ret = inject_touch_state(pressed);
    if (ret < 0) {
        uart_write_str("ERR touch inject failed");
        return;
    }

    uart_write_str(pressed ? "OK touch down" : "OK touch up");
}

static void process_move_command(char *args) {
    char *saveptr = NULL;
    char *dx_text = strtok_r(args, " ", &saveptr);
    char *dy_text = strtok_r(NULL, " ", &saveptr);

    if (!dx_text || !dy_text || strtok_r(NULL, " ", &saveptr)) {
        uart_write_str("ERR usage: move <dx> <dy>");
        return;
    }

    long dx = 0;
    long dy = 0;

    if (parse_long_arg(dx_text, &dx) < 0 || parse_long_arg(dy_text, &dy) < 0) {
        uart_write_str("ERR invalid move arguments");
        return;
    }

    int ret = inject_touch_move((int32_t)dx, (int32_t)dy);
    if (ret < 0) {
        uart_write_str("ERR move inject failed");
        return;
    }

    uart_write_str("OK move");
}

static void process_abs_command(char *args) {
    char *saveptr = NULL;
    char *x_text = strtok_r(args, " ", &saveptr);
    char *y_text = strtok_r(NULL, " ", &saveptr);

    if (!x_text || !y_text || strtok_r(NULL, " ", &saveptr)) {
        uart_write_str("ERR usage: abs <x> <y>");
        return;
    }

    long x = 0;
    long y = 0;

    if (parse_long_arg(x_text, &x) < 0 || parse_long_arg(y_text, &y) < 0) {
        uart_write_str("ERR invalid abs arguments");
        return;
    }

    int ret = inject_touch_abs((int32_t)x, (int32_t)y);
    if (ret < 0) {
        uart_write_str("ERR abs inject failed");
        return;
    }

    uart_write_str("OK abs");
}

/* ── Persistent gesture params (right side only) ─────────────────────────── */

#if defined(CONFIG_SHIELD_TOUCAN_RIGHT)

static const char *const pad_param_keys[] = {
    "tap_timeout_ms", "drag_window_timeout_ms", "drag_jump_timeout_ms",
    "pad_off_timeout_ms", "scroll_rim_percent", "drag_jump_rim_percent",
    "dead_radius_percent", "rclick_x_min_percent", "force_drag_z_threshold",
    "double_click_drag_z_threshold", "wheel_clicks", "scroll_exclusion_zone_percent",
    "tap_snap",
};

static bool pad_settings_loaded_any = false;

static int pad_settings_load_cb(const char *name, size_t len,
                                  settings_read_cb read_cb, void *cb_arg) {
    int32_t val;
    ssize_t rc = read_cb(cb_arg, &val, sizeof(val));
    if (rc != (ssize_t)sizeof(val)) {
        return (rc < 0) ? (int)rc : -EIO;
    }
    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(glidepoint));
    if (device_is_ready(dev)) {
        int ret = pinnacle_gesture_param_set(dev, name, val);
        if (ret < 0) {
            LOG_WRN("Unknown pad param in settings: %s", name);
        }
    }
    pad_settings_loaded_any = true;
    return 0;
}

/* Called after all settings are loaded.  On first boot (nothing saved yet),
 * persist the DTS defaults so they survive future firmware updates. */
static int pad_settings_commit_cb(void) {
    if (pad_settings_loaded_any) {
        return 0;
    }
    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(glidepoint));
    if (!device_is_ready(dev)) {
        return 0;
    }
    for (size_t i = 0; i < ARRAY_SIZE(pad_param_keys); i++) {
        int32_t val;
        if (pinnacle_gesture_param_get(dev, pad_param_keys[i], &val) == 0) {
            char path[64];
            snprintf(path, sizeof(path), "toucan/pad/%s", pad_param_keys[i]);
            settings_save_one(path, &val, sizeof(val));
        }
    }
    LOG_INF("Saved touchpad defaults to settings (first boot)");
    return 0;
}

SETTINGS_STATIC_HANDLER_DEFINE(toucan_pad, "toucan/pad", NULL,
                               pad_settings_load_cb, pad_settings_commit_cb, NULL);

static void process_get_command(char *args) {
    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(glidepoint));
    if (!device_is_ready(dev)) {
        uart_write_str("ERR touchpad not ready");
        return;
    }

    /* No arg → list all params as "OK get key=val key=val ..." on one line. */
    if (!args || *args == '\0') {
        /* Build response: "OK get " followed by key=val pairs. */
        const char *prefix = "OK get";
        for (const char *p = prefix; *p; p++) {
            uart_poll_out(debug_rpc_uart, *p);
        }
        for (size_t i = 0; i < ARRAY_SIZE(pad_param_keys); i++) {
            int32_t val;
            if (pinnacle_gesture_param_get(dev, pad_param_keys[i], &val) == 0) {
                char kv[48];
                snprintf(kv, sizeof(kv), " %s=%d", pad_param_keys[i], (int)val);
                for (const char *p = kv; *p; p++) {
                    uart_poll_out(debug_rpc_uart, *p);
                }
            }
        }
        uart_poll_out(debug_rpc_uart, '\r');
        uart_poll_out(debug_rpc_uart, '\n');
        return;
    }

    int32_t val;
    if (pinnacle_gesture_param_get(dev, args, &val) < 0) {
        uart_write_str("ERR unknown param");
        return;
    }
    char buf[80];
    snprintf(buf, sizeof(buf), "OK %s=%d", args, (int)val);
    uart_write_str(buf);
}

static void process_set_command(char *args) {
    char *saveptr = NULL;
    char *key = strtok_r(args, " ", &saveptr);
    char *val_text = strtok_r(NULL, " ", &saveptr);

    if (!key || !val_text || strtok_r(NULL, " ", &saveptr)) {
        uart_write_str("ERR usage: set <param> <value>");
        return;
    }

    long val;
    if (parse_long_arg(val_text, &val) < 0) {
        uart_write_str("ERR invalid value");
        return;
    }

    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(glidepoint));
    if (!device_is_ready(dev)) {
        uart_write_str("ERR touchpad not ready");
        return;
    }

    if (pinnacle_gesture_param_set(dev, key, (int32_t)val) < 0) {
        uart_write_str("ERR unknown param");
        return;
    }

    char path[64];
    snprintf(path, sizeof(path), "toucan/pad/%s", key);
    int32_t v32 = (int32_t)val;
    settings_save_one(path, &v32, sizeof(v32));

    char buf[80];
    snprintf(buf, sizeof(buf), "OK set %s=%d", key, (int)val);
    uart_write_str(buf);
}

#endif /* CONFIG_SHIELD_TOUCAN_RIGHT */

static void process_quarantine_command(char *args) {
    if (!args || *args == '\0' || strcmp(args, "status") == 0) {
        uart_write_str(toucan_debug_quarantine_is_enabled() ? "OK quarantine=on"
                                                            : "OK quarantine=off");
        return;
    }

    if (strcmp(args, "on") == 0) {
        toucan_debug_quarantine_set_enabled(true);
        uart_write_str("OK quarantine=on");
        return;
    }

    if (strcmp(args, "off") == 0) {
        toucan_debug_quarantine_set_enabled(false);
        uart_write_str("OK quarantine=off");
        return;
    }

    uart_write_str("ERR usage: quarantine <on|off|status>");
}

static void process_command(const struct toucan_debug_rpc_cmd *cmd) {
    LOG_DBG("Debug RPC command: %s", cmd->text);

    char command[TOUCAN_DEBUG_RPC_CMD_MAX_LEN];
    strncpy(command, cmd->text, sizeof(command) - 1);
    command[sizeof(command) - 1] = '\0';

    char *saveptr = NULL;
    char *verb = strtok_r(command, " ", &saveptr);
    char *args = saveptr;

    if (!verb) {
        uart_write_str("ERR empty");
        return;
    }

    if (strcmp(verb, "ping") == 0) {
        uart_write_identity("OK pong");
        return;
    }

    if (strcmp(verb, "identity") == 0) {
        uart_write_identity("OK");
        return;
    }

    if (strcmp(verb, "help") == 0) {
        uart_write_str(
            "OK commands: ping identity reset bootloader quarantine key tap touch abs move"
            " get set help");
        return;
    }

    if (strcmp(verb, "reset") == 0) {
        LOG_WRN("Reset requested over USB debug RPC");
        reset_after_reply();
        return;
    }

    if (strcmp(verb, "bootloader") == 0) {
        LOG_WRN("UF2 bootloader requested over USB debug RPC");
        bootloader_after_reply();
        return;
    }

    if (strcmp(verb, "key") == 0) {
        process_key_command(args);
        return;
    }

    if (strcmp(verb, "tap") == 0) {
        process_tap_command(args);
        return;
    }

    if (strcmp(verb, "touch") == 0) {
        process_touch_command(args);
        return;
    }

    if (strcmp(verb, "move") == 0) {
        process_move_command(args);
        return;
    }

    if (strcmp(verb, "abs") == 0) {
        process_abs_command(args);
        return;
    }

    if (strcmp(verb, "quarantine") == 0) {
        process_quarantine_command(args);
        return;
    }

    if (strcmp(verb, "get") == 0) {
#if defined(CONFIG_SHIELD_TOUCAN_RIGHT)
        process_get_command(args);
#else
        uart_write_str("ERR get/set only available on right half");
#endif
        return;
    }

    if (strcmp(verb, "set") == 0) {
#if defined(CONFIG_SHIELD_TOUCAN_RIGHT)
        process_set_command(args);
#else
        uart_write_str("ERR get/set only available on right half");
#endif
        return;
    }

    uart_write_str("ERR unknown");
}

static void toucan_debug_rpc_main(void *a, void *b, void *c) {
    ARG_UNUSED(a);
    ARG_UNUSED(b);
    ARG_UNUSED(c);

    struct toucan_debug_rpc_cmd cmd;

    for (;;) {
        if (k_msgq_get(&toucan_debug_rpc_cmdq, &cmd, K_FOREVER) == 0) {
            process_command(&cmd);
        }
    }
}

static int toucan_debug_rpc_init(void) {
    if (!device_is_ready(debug_rpc_uart)) {
        LOG_ERR("Toucan debug RPC UART not ready");
        return -ENODEV;
    }

    int ret = uart_irq_callback_user_data_set(debug_rpc_uart, uart_cb, NULL);
    if (ret < 0) {
        LOG_ERR("Failed to register debug RPC UART callback: %d", ret);
        return ret;
    }

    k_thread_create(&toucan_debug_rpc_thread, toucan_debug_rpc_stack,
                    K_THREAD_STACK_SIZEOF(toucan_debug_rpc_stack), toucan_debug_rpc_main, NULL,
                    NULL, NULL, K_LOWEST_APPLICATION_THREAD_PRIO, 0, K_NO_WAIT);
    k_thread_name_set(&toucan_debug_rpc_thread, "toucan_dbg_rpc");

    uart_irq_rx_enable(debug_rpc_uart);

    LOG_INF("Toucan debug RPC ready (%s %s)", TOUCAN_DEBUG_RPC_SIDE, TOUCAN_DEBUG_RPC_ROLE);
    return 0;
}

SYS_INIT(toucan_debug_rpc_init, POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT);
