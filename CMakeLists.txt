# CMAKE_ASM_COMPILER_LAUNCHER is consumed by CMake's Ninja generator (C++ code)
# to prepend the launcher to ASM compile rules. The cmake script layer never
# reads it, so CMake wrongly reports "not used". Reference it here to silence
# that spurious warning without changing any build behaviour.
if(CMAKE_ASM_COMPILER_LAUNCHER)
endif()

zephyr_include_directories(include)

target_sources_ifdef(CONFIG_TOUCAN_DEBUG_RPC app PRIVATE
  src/debug_rpc.c
  src/behavior_debug_inject.c)
target_sources_ifdef(CONFIG_TOUCAN_DEBUG_QUARANTINE app PRIVATE
  src/debug_quarantine.c)
if(CONFIG_TOUCAN_DEBUG_QUARANTINE)
  zephyr_link_libraries(
    -Wl,--wrap=zmk_endpoints_send_report
    -Wl,--wrap=zmk_endpoints_send_mouse_report)
endif()

if ((NOT CONFIG_ZMK_SPLIT) OR CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
  target_sources_ifdef(CONFIG_TOUCAN_DEBUG_RPC app PRIVATE
    src/debug_pad_trace.c)
  target_sources_ifdef(CONFIG_ZMK_BEHAVIOR_LEADER_KEY app PRIVATE
    src/leader_sanity.c)
  target_sources(app PRIVATE
    src/events/text_mode_changed.c
    src/toucan_text_state.c)
  target_sources_ifdef(CONFIG_ZMK_BEHAVIOR_TOUCAN_OUTPUT_MODE app PRIVATE
    src/behaviors/behavior_toucan_output_mode.c)
  target_sources_ifdef(CONFIG_ZMK_BEHAVIOR_TOUCAN_TEXT_SYMBOL app PRIVATE
    src/behaviors/behavior_toucan_text_symbol.c)
  target_sources_ifdef(CONFIG_ZMK_BEHAVIOR_TOUCAN_CLIPBOARD app PRIVATE
    src/behaviors/behavior_toucan_clipboard.c)
endif()


