#pragma once

#include <stdbool.h>
#include <stdint.h>

#include <dt-bindings/zmk-toucan/text.h>

enum toucan_text_greek_mode {
    TOUCAN_GREEK_MODE_UNICODE = 0,
    TOUCAN_GREEK_MODE_LATEX = 1,
};

uint8_t toucan_text_mode_get_current(void);
uint8_t toucan_text_greek_mode_get_current(void);
bool toucan_text_greek_uses_latex_current(void);

int toucan_text_mode_set_current(uint8_t host_mode);
int toucan_text_mode_cycle_current(void);
int toucan_text_greek_mode_toggle_current(void);
int toucan_text_sync_current_unicode_mode(void);
