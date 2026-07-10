/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: MIT
 *
 * Persistent rotating log of per-half activity (active/idle) and charging
 * durations. Records are 2-byte packed entries stored as a page-ring in the
 * NVS settings partition (`tsl/<n>` keys) so the history survives deep sleep.
 * See plans/2026-06-26-right-half-sleep-investigation.md (§3c) for the design.
 */

#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Record bit layout (uint16):
 *   [1:0]  activity state  (0=ACTIVE, 1=IDLE, 2=SLEEP marker)
 *   [2]    charging        (1 = USB power present)
 *   [15:3] duration in seconds (0..8191, saturating)
 */
#define TOUCAN_SLEEP_LOG_STATE_MASK 0x3
#define TOUCAN_SLEEP_LOG_CHG_BIT    (1u << 2)
#define TOUCAN_SLEEP_LOG_DUR_SHIFT  3
#define TOUCAN_SLEEP_LOG_MAX_DUR_S  0x1FFF

#define TOUCAN_SLEEP_LOG_PAGE_RECORDS 42
#define TOUCAN_SLEEP_LOG_NUM_PAGES    32

/* On-flash / in-RAM page layout (88 bytes). */
struct toucan_sleep_log_page {
    uint16_t seq;   /* monotonic page sequence; higher == newer */
    uint8_t count;  /* number of valid records (0..PAGE_RECORDS) */
    uint8_t rsvd;
    uint16_t rec[TOUCAN_SLEEP_LOG_PAGE_RECORDS];
} __packed;

/* Ring slot the current (open) page is being written to. */
uint8_t toucan_sleep_log_cur_slot(void);

/* Force the current (open) page to NVS now. Records the in-flight segment's
 * elapsed time first. Used to checkpoint on demand and to prove that the log
 * survives a reboot. Returns 0 on success or a negative errno. */
int toucan_sleep_log_flush(void);

/* Fetch one page by ring slot (0..NUM_PAGES-1). The current slot is served from
 * the in-RAM shadow; others are read from NVS. Returns true if `out` was filled.
 * Pages are read individually (one RPC line each) so the host can reassemble
 * chronological order by sorting on `seq`. */
bool toucan_sleep_log_get_page(uint8_t slot, struct toucan_sleep_log_page *out);
