#pragma once

#include <lvgl.h>
#include "util.h"

void draw_profile_status(lv_obj_t *canvas, const struct status_state *state);

/* True while the selected profile is advertising (not connected) -- either
 * reconnecting to a stored bond or open and waiting to pair. Drives the blink. */
bool profile_status_advertising(void);

/* Advance the blink phase; call periodically while connecting. */
void profile_status_blink_toggle(void);
