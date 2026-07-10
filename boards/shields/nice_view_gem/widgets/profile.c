#include <zephyr/kernel.h>
#include <zmk/ble.h>
#include "profile.h"

LV_IMG_DECLARE(profiles);

/* The `profiles` image draws ZMK_BLE_PROFILE_COUNT empty 8x8 outline boxes,
 * spaced 10px apart, at this origin. Each box is split into two independent
 * halves, one per lifecycle:
 *   - pairing half (left):     empty unpaired -> blink while pairing -> solid paired
 *   - connection half (right): empty disconnected -> blink while connecting -> solid connected */
#define PROFILE_ORIGIN_X 85
#define PROFILE_ORIGIN_Y 143
#define PROFILE_SPACING  10
#define PROFILE_BOX      8
#define PROFILE_HALF     (PROFILE_BOX / 2)

/* Blink phase toggled by screen.c while the selected slot is advertising.
 * Starts filled so an advertising slot reads as "lit" on its first frame. */
static bool blink_on = true;

/* The selected profile is the only slot ZMK advertises for: if it is not
 * connected, a link attempt is in flight -- either reconnecting to a stored
 * bond, or open and waiting for a new device to pair. Both blink. */
bool profile_status_advertising(void) {
    int selected = zmk_ble_active_profile_index();
    if (selected < 0 || selected >= ZMK_BLE_PROFILE_COUNT) {
        return false;
    }
    return !zmk_ble_profile_is_connected(selected);
}

void profile_status_blink_toggle(void) {
    blink_on = !blink_on;
}

static void draw_box_outlines(lv_obj_t *canvas) {
    lv_draw_img_dsc_t img_dsc;
    lv_draw_img_dsc_init(&img_dsc);
    lv_canvas_draw_img(canvas, PROFILE_ORIGIN_X, PROFILE_ORIGIN_Y, &profiles, &img_dsc);
}

static void fill_rect(lv_obj_t *canvas, int x, int y, int w, int h) {
    lv_draw_rect_dsc_t rect_dsc;
    init_rect_dsc(&rect_dsc, LVGL_FOREGROUND);
    lv_canvas_draw_rect(canvas, x, y, w, h, &rect_dsc);
}

/*
 * Per-slot indicator, drawn over the outline box. Left half = pairing,
 * right half = connection:
 *   not paired, idle       -> empty outline
 *   pairing (selected open) -> left half blinks
 *   paired, disconnected    -> left half solid
 *   reconnecting (selected) -> left half solid, right half blinks
 *   paired, connected       -> fully filled
 * The selected slot is additionally underlined.
 */
void draw_profile_status(lv_obj_t *canvas, const struct status_state *state) {
    draw_box_outlines(canvas);

    int selected = state->active_profile_index;

    for (int i = 0; i < ZMK_BLE_PROFILE_COUNT; i++) {
        int x = PROFILE_ORIGIN_X + i * PROFILE_SPACING;
        int y = PROFILE_ORIGIN_Y;
        int left = x;
        int right = x + PROFILE_HALF;

        bool bonded = !zmk_ble_profile_is_open(i);
        bool connected = zmk_ble_profile_is_connected(i);
        bool selected_slot = (i == selected);

        /* Left half (pairing): solid once paired, blinking while a selected
         * open slot advertises for a new device to pair. */
        if (bonded) {
            fill_rect(canvas, left, y, PROFILE_HALF, PROFILE_BOX);
        } else if (selected_slot && blink_on) {
            fill_rect(canvas, left, y, PROFILE_HALF, PROFILE_BOX);
        }

        /* Right half (connection): solid when connected, blinking while a
         * selected paired slot is trying to reconnect. */
        if (connected) {
            fill_rect(canvas, right, y, PROFILE_HALF, PROFILE_BOX);
        } else if (bonded && selected_slot && blink_on) {
            fill_rect(canvas, right, y, PROFILE_HALF, PROFILE_BOX);
        }

        if (selected_slot) {
            fill_rect(canvas, x, y + PROFILE_BOX + 1, PROFILE_BOX, 1);
        }
    }
}
