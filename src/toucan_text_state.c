#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>

#include <zmk/behavior.h>
#include <zmk/ble.h>
#include <zmk/endpoints.h>
#include <zmk/event_manager.h>
#include <zmk/events/endpoint_changed.h>

#include <dt-bindings/zmk-unicode/uc.h>

#include <zmk-toucan/text_state.h>
#include <zmk-toucan/events/text_mode_changed.h>

LOG_MODULE_REGISTER(toucan_text_state, CONFIG_ZMK_LOG_LEVEL);

#ifdef DT_N_NODELABEL_uc
#define TOUCAN_UNICODE_BEHAVIOR_DEV DEVICE_DT_NAME(DT_NODELABEL(uc))
#else
#define TOUCAN_UNICODE_BEHAVIOR_DEV "unicode"
#endif

struct toucan_text_profile_state {
    uint8_t host_mode;
    uint8_t greek_mode;
};

#define TOUCAN_TEXT_DEFAULT_HOST_MODE TOUCAN_TEXT_MODE_MACOS
#define TOUCAN_TEXT_DEFAULT_GREEK_MODE TOUCAN_GREEK_MODE_UNICODE
#define TOUCAN_TEXT_DEFAULT_PROFILE_STATE                                                     \
    {                                                                                         \
        .host_mode = TOUCAN_TEXT_DEFAULT_HOST_MODE, .greek_mode = TOUCAN_TEXT_DEFAULT_GREEK_MODE \
    }

static struct toucan_text_profile_state usb_state = TOUCAN_TEXT_DEFAULT_PROFILE_STATE;

#if IS_ENABLED(CONFIG_ZMK_BLE)
static struct toucan_text_profile_state ble_states[ZMK_BLE_PROFILE_COUNT] = {
    [0 ... ZMK_BLE_PROFILE_COUNT - 1] = TOUCAN_TEXT_DEFAULT_PROFILE_STATE,
};
#endif

static void normalize_state(struct toucan_text_profile_state *state) {
    if (state->host_mode > TOUCAN_TEXT_MODE_IOS) {
        state->host_mode = TOUCAN_TEXT_DEFAULT_HOST_MODE;
    }

    if (state->greek_mode > TOUCAN_GREEK_MODE_LATEX) {
        state->greek_mode = TOUCAN_TEXT_DEFAULT_GREEK_MODE;
    }
}

static struct toucan_text_profile_state *state_for_endpoint(struct zmk_endpoint_instance endpoint) {
    switch (endpoint.transport) {
    case ZMK_TRANSPORT_USB:
        return &usb_state;
    case ZMK_TRANSPORT_BLE:
#if IS_ENABLED(CONFIG_ZMK_BLE)
        if (endpoint.ble.profile_index < ZMK_BLE_PROFILE_COUNT) {
            return &ble_states[endpoint.ble.profile_index];
        }
#endif
        return NULL;
    default:
        return NULL;
    }
}

static struct toucan_text_profile_state *current_state(void) {
    return state_for_endpoint(zmk_endpoints_selected());
}

static const char *host_mode_name(uint8_t host_mode) {
    switch (host_mode) {
    case TOUCAN_TEXT_MODE_MACOS:
        return "macos";
    case TOUCAN_TEXT_MODE_IOS:
        return "ios";
    case TOUCAN_TEXT_MODE_LINUX:
    default:
        return "linux";
    }
}

static const char *greek_mode_name(uint8_t greek_mode) {
    switch (greek_mode) {
    case TOUCAN_GREEK_MODE_LATEX:
        return "latex";
    case TOUCAN_GREEK_MODE_UNICODE:
    default:
        return "unicode";
    }
}

static void log_current_state(const char *action, struct zmk_endpoint_instance endpoint,
                              const struct toucan_text_profile_state *state) {
    char endpoint_str[ZMK_ENDPOINT_STR_LEN] = {0};

    zmk_endpoint_instance_to_str(endpoint, endpoint_str, sizeof(endpoint_str));
    LOG_INF("%s endpoint=%s host=%s greek=%s", action, endpoint_str,
            host_mode_name(state->host_mode), greek_mode_name(state->greek_mode));
}

static uint8_t unicode_mode_for_host_mode(uint8_t host_mode) {
    switch (host_mode) {
    case TOUCAN_TEXT_MODE_MACOS:
        return UC_MODE_MACOS;
    case TOUCAN_TEXT_MODE_IOS:
        return UC_MODE_MACOS;
    case TOUCAN_TEXT_MODE_LINUX:
    default:
        return UC_MODE_LINUX;
    }
}

static int sync_unicode_mode_for_endpoint(struct zmk_endpoint_instance endpoint) {
    struct toucan_text_profile_state *state = state_for_endpoint(endpoint);

    if (!state) {
        return -EINVAL;
    }

    struct zmk_behavior_binding binding = {
        .behavior_dev = TOUCAN_UNICODE_BEHAVIOR_DEV,
        .param1 = UC_SELECT_INPUT_MODE,
        .param2 = unicode_mode_for_host_mode(state->host_mode),
    };
    struct zmk_behavior_binding_event event = {
        .position = UINT32_MAX,
        .timestamp = k_uptime_get(),
#if IS_ENABLED(CONFIG_ZMK_SPLIT)
        .source = 0,
#endif
    };

    LOG_DBG("Sync unicode endpoint transport=%u host=%s greek=%s uc_mode=%u", endpoint.transport,
            host_mode_name(state->host_mode), greek_mode_name(state->greek_mode), binding.param2);

    return zmk_behavior_invoke_binding(&binding, event, true);
}

static int save_current_state(void) {
#if IS_ENABLED(CONFIG_SETTINGS)
    struct zmk_endpoint_instance endpoint = zmk_endpoints_selected();
    struct toucan_text_profile_state *state = state_for_endpoint(endpoint);

    if (!state) {
        return -EINVAL;
    }

    switch (endpoint.transport) {
    case ZMK_TRANSPORT_USB:
        return settings_save_one("toucan_text/usb", state, sizeof(*state));
    case ZMK_TRANSPORT_BLE:
#if IS_ENABLED(CONFIG_ZMK_BLE)
        char setting_name[32];
        snprintf(setting_name, sizeof(setting_name), "toucan_text/ble/%u",
                 endpoint.ble.profile_index);
        return settings_save_one(setting_name, state, sizeof(*state));
#else
        return -ENOTSUP;
#endif
    default:
        return -EINVAL;
    }
#else
    return 0;
#endif
}

uint8_t toucan_text_mode_get_current(void) {
    struct toucan_text_profile_state *state = current_state();
    return state ? state->host_mode : TOUCAN_TEXT_DEFAULT_HOST_MODE;
}

uint8_t toucan_text_greek_mode_get_current(void) {
    struct toucan_text_profile_state *state = current_state();
    return state ? state->greek_mode : TOUCAN_TEXT_DEFAULT_GREEK_MODE;
}

bool toucan_text_greek_uses_latex_current(void) {
    return toucan_text_mode_get_current() == TOUCAN_TEXT_MODE_IOS ||
           toucan_text_greek_mode_get_current() == TOUCAN_GREEK_MODE_LATEX;
}

int toucan_text_sync_current_unicode_mode(void) {
    return sync_unicode_mode_for_endpoint(zmk_endpoints_selected());
}

int toucan_text_mode_set_current(uint8_t host_mode) {
    struct zmk_endpoint_instance endpoint = zmk_endpoints_selected();
    struct toucan_text_profile_state *state = current_state();

    if (!state || host_mode > TOUCAN_TEXT_MODE_IOS) {
        return -EINVAL;
    }

    state->host_mode = host_mode;

    int err = save_current_state();
    if (err < 0) {
        return err;
    }

    err = toucan_text_sync_current_unicode_mode();
    if (err < 0) {
        return err;
    }

    log_current_state("Updated text mode", endpoint, state);
    raise_toucan_text_mode_changed(host_mode);
    return 0;
}

int toucan_text_mode_cycle_current(void) {
    uint8_t next_mode = (toucan_text_mode_get_current() + 1) % 3;
    return toucan_text_mode_set_current(next_mode);
}

int toucan_text_greek_mode_toggle_current(void) {
    struct zmk_endpoint_instance endpoint = zmk_endpoints_selected();
    struct toucan_text_profile_state *state = current_state();

    if (!state) {
        return -EINVAL;
    }

    state->greek_mode = (state->greek_mode == TOUCAN_GREEK_MODE_UNICODE)
                            ? TOUCAN_GREEK_MODE_LATEX
                            : TOUCAN_GREEK_MODE_UNICODE;

    int err = save_current_state();
    if (err < 0) {
        return err;
    }

    log_current_state("Updated greek mode", endpoint, state);
    return 0;
}

static int toucan_text_settings_set(const char *name, size_t len, settings_read_cb read_cb,
                                    void *cb_arg) {
    const char *next;
    struct toucan_text_profile_state state = TOUCAN_TEXT_DEFAULT_PROFILE_STATE;

    if (settings_name_steq(name, "usb", &next) && !next) {
        if (len != sizeof(state)) {
            return -EINVAL;
        }

        int err = read_cb(cb_arg, &state, len);
        if (err <= 0) {
            return err;
        }

        normalize_state(&state);
        usb_state = state;
        return 0;
    }

#if IS_ENABLED(CONFIG_ZMK_BLE)
    if (settings_name_steq(name, "ble", &next) && next) {
        char *endptr = NULL;
        long index = strtol(next, &endptr, 10);

        if (*next == '\0' || !endptr || *endptr != '\0') {
            return -EINVAL;
        }

        if (index < 0 || index >= ZMK_BLE_PROFILE_COUNT) {
            return -EINVAL;
        }

        if (len != sizeof(state)) {
            return -EINVAL;
        }

        int err = read_cb(cb_arg, &state, len);
        if (err <= 0) {
            return err;
        }

        normalize_state(&state);
        ble_states[index] = state;
        return 0;
    }
#endif

    return 0;
}

static int toucan_text_settings_commit(void) { return toucan_text_sync_current_unicode_mode(); }

SETTINGS_STATIC_HANDLER_DEFINE(toucan_text, "toucan_text", NULL, toucan_text_settings_set,
                               toucan_text_settings_commit, NULL);

static int toucan_text_endpoint_listener(const zmk_event_t *eh) {
    const struct zmk_endpoint_changed *ev = as_zmk_endpoint_changed(eh);

    if (!ev) {
        return -ENOTSUP;
    }

    return sync_unicode_mode_for_endpoint(ev->endpoint);
}

ZMK_LISTENER(toucan_text_endpoint_listener, toucan_text_endpoint_listener);
ZMK_SUBSCRIPTION(toucan_text_endpoint_listener, zmk_endpoint_changed);
