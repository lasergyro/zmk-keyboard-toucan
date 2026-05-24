#include <zephyr/devicetree.h>

#if DT_NODE_EXISTS(DT_NODELABEL(leader))
#include <zephyr/sys/util.h>

#define TOUCAN_LEADER_CHILD_ARG(node_id) 1
#define TOUCAN_LEADER_SEQUENCE_COUNT                                                           \
    NUM_VA_ARGS_LESS_1(_,                                                                     \
                       DT_FOREACH_CHILD_SEP(DT_NODELABEL(leader), TOUCAN_LEADER_CHILD_ARG,   \
                                            (,)))

BUILD_ASSERT(
    TOUCAN_LEADER_SEQUENCE_COUNT <= CONFIG_ZMK_LEADER_MAX_SEQUENCES,
    "Leader sequence count exceeds CONFIG_ZMK_LEADER_MAX_SEQUENCES. Increase the limit or remove "
    "leader sequences.");
#endif
