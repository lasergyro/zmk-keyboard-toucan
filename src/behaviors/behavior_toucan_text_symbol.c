#define DT_DRV_COMPAT zmk_behavior_toucan_text_symbol

#include <ctype.h>

#include <drivers/behavior.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>

#include <zmk/behavior.h>
#include <zmk/behavior_queue.h>
#include <zmk/hid.h>

#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk-toucan/text.h>

#include <zmk-toucan/text_state.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#ifdef DT_N_NODELABEL_kp
#define TOUCAN_KEY_PRESS_BEHAVIOR_DEV DEVICE_DT_NAME(DT_NODELABEL(kp))
#else
#define TOUCAN_KEY_PRESS_BEHAVIOR_DEV "key_press"
#endif

#ifdef DT_N_NODELABEL_mask_mods
#define TOUCAN_MASK_MODS_BEHAVIOR_DEV DEVICE_DT_NAME(DT_NODELABEL(mask_mods))
#else
#define TOUCAN_MASK_MODS_BEHAVIOR_DEV "mask_mods"
#endif

#ifdef DT_N_NODELABEL_uc
#define TOUCAN_UNICODE_BEHAVIOR_DEV DEVICE_DT_NAME(DT_NODELABEL(uc))
#else
#define TOUCAN_UNICODE_BEHAVIOR_DEV "unicode"
#endif

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

#define TOUCAN_ALL_MODS                                                                       \
    (MOD_LSFT | MOD_RSFT | MOD_LCTL | MOD_RCTL | MOD_LALT | MOD_RALT | MOD_LGUI | MOD_RGUI)

struct toucan_text_symbol_def {
    uint32_t lower;
    uint32_t upper;
    const char *latex_name;
    zmk_key_t apple_lower_1;
    zmk_key_t apple_lower_2;
    zmk_key_t apple_upper_1;
    zmk_key_t apple_upper_2;
};

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

static const char *symbol_output_path_name(bool use_latex, bool use_apple) {
    if (use_latex) {
        return "latex";
    }

    if (use_apple) {
        return "apple";
    }

    return "unicode";
}

static const struct toucan_text_symbol_def *lookup_symbol(uint32_t symbol) {
    switch (symbol) {
    case TOUCAN_TEXT_SYMBOL_DE_AE:
        static const struct toucan_text_symbol_def de_ae = {
            .lower = 0x00e4,
            .upper = 0x00c4,
            .apple_lower_1 = LA(U),
            .apple_lower_2 = A,
            .apple_upper_1 = LA(U),
            .apple_upper_2 = LS(A),
        };
        return &de_ae;
    case TOUCAN_TEXT_SYMBOL_DE_OE:
        static const struct toucan_text_symbol_def de_oe = {
            .lower = 0x00f6,
            .upper = 0x00d6,
            .apple_lower_1 = LA(U),
            .apple_lower_2 = O,
            .apple_upper_1 = LA(U),
            .apple_upper_2 = LS(O),
        };
        return &de_oe;
    case TOUCAN_TEXT_SYMBOL_DE_UE:
        static const struct toucan_text_symbol_def de_ue = {
            .lower = 0x00fc,
            .upper = 0x00dc,
            .apple_lower_1 = LA(U),
            .apple_lower_2 = U,
            .apple_upper_1 = LA(U),
            .apple_upper_2 = LS(U),
        };
        return &de_ue;
    case TOUCAN_TEXT_SYMBOL_DE_SS:
        static const struct toucan_text_symbol_def de_ss = {
            .lower = 0x00df,
            .upper = 0x1e9e,
            .apple_lower_1 = LA(S),
            .apple_upper_1 = LA(S),
        };
        return &de_ss;
    case TOUCAN_TEXT_SYMBOL_EL_ALPHA:
        static const struct toucan_text_symbol_def el_alpha = {
            .lower = 0x03b1, .upper = 0x0391, .latex_name = "alpha"};
        return &el_alpha;
    case TOUCAN_TEXT_SYMBOL_EL_BETA:
        static const struct toucan_text_symbol_def el_beta = {
            .lower = 0x03b2, .upper = 0x0392, .latex_name = "beta"};
        return &el_beta;
    case TOUCAN_TEXT_SYMBOL_EL_GAMMA:
        static const struct toucan_text_symbol_def el_gamma = {
            .lower = 0x03b3, .upper = 0x0393, .latex_name = "gamma"};
        return &el_gamma;
    case TOUCAN_TEXT_SYMBOL_EL_DELTA:
        static const struct toucan_text_symbol_def el_delta = {
            .lower = 0x03b4, .upper = 0x0394, .latex_name = "delta"};
        return &el_delta;
    case TOUCAN_TEXT_SYMBOL_EL_EPSILON:
        static const struct toucan_text_symbol_def el_epsilon = {
            .lower = 0x03b5, .upper = 0x0395, .latex_name = "epsilon"};
        return &el_epsilon;
    case TOUCAN_TEXT_SYMBOL_EL_ZETA:
        static const struct toucan_text_symbol_def el_zeta = {
            .lower = 0x03b6, .upper = 0x0396, .latex_name = "zeta"};
        return &el_zeta;
    case TOUCAN_TEXT_SYMBOL_EL_ETA:
        static const struct toucan_text_symbol_def el_eta = {
            .lower = 0x03b7, .upper = 0x0397, .latex_name = "eta"};
        return &el_eta;
    case TOUCAN_TEXT_SYMBOL_EL_THETA:
        static const struct toucan_text_symbol_def el_theta = {
            .lower = 0x03b8, .upper = 0x0398, .latex_name = "theta"};
        return &el_theta;
    case TOUCAN_TEXT_SYMBOL_EL_IOTA:
        static const struct toucan_text_symbol_def el_iota = {
            .lower = 0x03b9, .upper = 0x0399, .latex_name = "iota"};
        return &el_iota;
    case TOUCAN_TEXT_SYMBOL_EL_KAPPA:
        static const struct toucan_text_symbol_def el_kappa = {
            .lower = 0x03ba, .upper = 0x039a, .latex_name = "kappa"};
        return &el_kappa;
    case TOUCAN_TEXT_SYMBOL_EL_LAMBDA:
        static const struct toucan_text_symbol_def el_lambda = {
            .lower = 0x03bb, .upper = 0x039b, .latex_name = "lambda"};
        return &el_lambda;
    case TOUCAN_TEXT_SYMBOL_EL_MU:
        static const struct toucan_text_symbol_def el_mu = {
            .lower = 0x03bc, .upper = 0x039c, .latex_name = "mu"};
        return &el_mu;
    case TOUCAN_TEXT_SYMBOL_EL_NU:
        static const struct toucan_text_symbol_def el_nu = {
            .lower = 0x03bd, .upper = 0x039d, .latex_name = "nu"};
        return &el_nu;
    case TOUCAN_TEXT_SYMBOL_EL_XI:
        static const struct toucan_text_symbol_def el_xi = {
            .lower = 0x03be, .upper = 0x039e, .latex_name = "xi"};
        return &el_xi;
    case TOUCAN_TEXT_SYMBOL_EL_OMIKRON:
        static const struct toucan_text_symbol_def el_omikron = {
            .lower = 0x03bf, .upper = 0x039f, .latex_name = "omikron"};
        return &el_omikron;
    case TOUCAN_TEXT_SYMBOL_EL_PI:
        static const struct toucan_text_symbol_def el_pi = {
            .lower = 0x03c0, .upper = 0x03a0, .latex_name = "pi"};
        return &el_pi;
    case TOUCAN_TEXT_SYMBOL_EL_RHO:
        static const struct toucan_text_symbol_def el_rho = {
            .lower = 0x03c1, .upper = 0x03a1, .latex_name = "rho"};
        return &el_rho;
    case TOUCAN_TEXT_SYMBOL_EL_SIGMA:
        static const struct toucan_text_symbol_def el_sigma = {
            .lower = 0x03c3, .upper = 0x03a3, .latex_name = "sigma"};
        return &el_sigma;
    case TOUCAN_TEXT_SYMBOL_EL_TAU:
        static const struct toucan_text_symbol_def el_tau = {
            .lower = 0x03c4, .upper = 0x03a4, .latex_name = "tau"};
        return &el_tau;
    case TOUCAN_TEXT_SYMBOL_EL_UPSILON:
        static const struct toucan_text_symbol_def el_upsilon = {
            .lower = 0x03c5, .upper = 0x03a5, .latex_name = "upsilon"};
        return &el_upsilon;
    case TOUCAN_TEXT_SYMBOL_EL_PHI:
        static const struct toucan_text_symbol_def el_phi = {
            .lower = 0x03d5, .upper = 0x03a6, .latex_name = "varphi"};
        return &el_phi;
    case TOUCAN_TEXT_SYMBOL_EL_CHI:
        static const struct toucan_text_symbol_def el_chi = {
            .lower = 0x03c7, .upper = 0x03a7, .latex_name = "chi"};
        return &el_chi;
    case TOUCAN_TEXT_SYMBOL_EL_PSI:
        static const struct toucan_text_symbol_def el_psi = {
            .lower = 0x03c8, .upper = 0x03a8, .latex_name = "psi"};
        return &el_psi;
    case TOUCAN_TEXT_SYMBOL_EL_OMEGA:
        static const struct toucan_text_symbol_def el_omega = {
            .lower = 0x03c9, .upper = 0x03a9, .latex_name = "omega"};
        return &el_omega;
    default:
        return NULL;
    }
}

static zmk_key_t ascii_to_key(char c) {
    switch (c) {
    case '\\':
        return BSLH;
    case 'a':
        return A;
    case 'b':
        return B;
    case 'c':
        return C;
    case 'd':
        return D;
    case 'e':
        return E;
    case 'f':
        return F;
    case 'g':
        return G;
    case 'h':
        return H;
    case 'i':
        return I;
    case 'j':
        return J;
    case 'k':
        return K;
    case 'l':
        return L;
    case 'm':
        return M;
    case 'n':
        return N;
    case 'o':
        return O;
    case 'p':
        return P;
    case 'q':
        return Q;
    case 'r':
        return R;
    case 's':
        return S;
    case 't':
        return T;
    case 'u':
        return U;
    case 'v':
        return V;
    case 'w':
        return W;
    case 'x':
        return X;
    case 'y':
        return Y;
    case 'z':
        return Z;
    case 'A':
        return LS(A);
    case 'B':
        return LS(B);
    case 'C':
        return LS(C);
    case 'D':
        return LS(D);
    case 'E':
        return LS(E);
    case 'F':
        return LS(F);
    case 'G':
        return LS(G);
    case 'H':
        return LS(H);
    case 'I':
        return LS(I);
    case 'J':
        return LS(J);
    case 'K':
        return LS(K);
    case 'L':
        return LS(L);
    case 'M':
        return LS(M);
    case 'N':
        return LS(N);
    case 'O':
        return LS(O);
    case 'P':
        return LS(P);
    case 'Q':
        return LS(Q);
    case 'R':
        return LS(R);
    case 'S':
        return LS(S);
    case 'T':
        return LS(T);
    case 'U':
        return LS(U);
    case 'V':
        return LS(V);
    case 'W':
        return LS(W);
    case 'X':
        return LS(X);
    case 'Y':
        return LS(Y);
    case 'Z':
        return LS(Z);
    default:
        return 0;
    }
}

static void queue_mask_mods(const struct zmk_behavior_binding_event *event,
                            struct zmk_behavior_binding *binding, zmk_mod_flags_t mods) {
    *binding =
        (struct zmk_behavior_binding){.behavior_dev = TOUCAN_MASK_MODS_BEHAVIOR_DEV, .param1 = mods};
    zmk_behavior_queue_add(event, *binding, true, 0);
}

static void queue_key_press(const struct zmk_behavior_binding_event *event,
                            struct zmk_behavior_binding *binding, zmk_key_t key) {
    *binding =
        (struct zmk_behavior_binding){.behavior_dev = TOUCAN_KEY_PRESS_BEHAVIOR_DEV, .param1 = key};
    zmk_behavior_queue_add(event, *binding, true, CONFIG_ZMK_UNICODE_TAP_MS);
}

static void queue_key_release(const struct zmk_behavior_binding_event *event,
                              struct zmk_behavior_binding *binding, zmk_key_t key) {
    *binding =
        (struct zmk_behavior_binding){.behavior_dev = TOUCAN_KEY_PRESS_BEHAVIOR_DEV, .param1 = key};
    zmk_behavior_queue_add(event, *binding, false, CONFIG_ZMK_UNICODE_WAIT_MS);
}

static void queue_key_tap(const struct zmk_behavior_binding_event *event,
                          struct zmk_behavior_binding *binding, zmk_key_t key) {
    queue_key_press(event, binding, key);
    queue_key_release(event, binding, key);
}

static int emit_masked_key_sequence(const struct zmk_behavior_binding_event *event, zmk_key_t key1,
                                    zmk_key_t key2) {
    struct zmk_behavior_binding binding;

    queue_mask_mods(event, &binding, TOUCAN_ALL_MODS);
    if (key1 != 0) {
        queue_key_tap(event, &binding, key1);
    }
    if (key2 != 0) {
        queue_key_tap(event, &binding, key2);
    }
    queue_mask_mods(event, &binding, 0);

    return 0;
}

static int emit_latex_symbol(const struct zmk_behavior_binding_event *event, const char *name,
                             bool shifted) {
    struct zmk_behavior_binding binding;

    queue_mask_mods(event, &binding, TOUCAN_ALL_MODS);
    queue_key_tap(event, &binding, ascii_to_key('\\'));

    for (size_t i = 0; name[i] != '\0'; i++) {
        char c = name[i];

        if (shifted && i == 0) {
            c = (char)toupper((unsigned char)c);
        }

        zmk_key_t key = ascii_to_key(c);
        if (key == 0) {
            queue_mask_mods(event, &binding, 0);
            return -EINVAL;
        }

        queue_key_tap(event, &binding, key);
    }

    queue_mask_mods(event, &binding, 0);
    return 0;
}

static int invoke_unicode_symbol(const struct zmk_behavior_binding_event *event, uint32_t lower,
                                 uint32_t upper) {
    int err = toucan_text_sync_current_unicode_mode();
    if (err < 0) {
        return err;
    }

    struct zmk_behavior_binding binding = {
        .behavior_dev = TOUCAN_UNICODE_BEHAVIOR_DEV,
        .param1 = lower,
        .param2 = upper,
    };

    return zmk_behavior_invoke_binding(&binding, *event, true);
}

static int on_text_symbol_pressed(struct zmk_behavior_binding *binding,
                                  struct zmk_behavior_binding_event event) {
    const struct toucan_text_symbol_def *symbol = lookup_symbol(binding->param1);
    const bool shifted = (zmk_hid_get_explicit_mods() & (MOD_LSFT | MOD_RSFT)) != 0;
    const uint8_t host_mode = toucan_text_mode_get_current();
    const uint8_t greek_mode = toucan_text_greek_mode_get_current();
    const bool use_latex = symbol && symbol->latex_name &&
                           (host_mode == TOUCAN_TEXT_MODE_IOS ||
                            greek_mode == TOUCAN_GREEK_MODE_LATEX);
    const bool use_apple = symbol && host_mode == TOUCAN_TEXT_MODE_IOS &&
                           symbol->apple_lower_1 != 0;

    if (!symbol) {
        LOG_ERR("Unknown Toucan text symbol: %u", binding->param1);
        return -EINVAL;
    }

    LOG_DBG("txtsym symbol=%u shifted=%d host=%s greek=%s path=%s", binding->param1, shifted,
            host_mode_name(host_mode), greek_mode_name(greek_mode),
            symbol_output_path_name(use_latex, use_apple));

    if (use_latex) {
        return emit_latex_symbol(&event, symbol->latex_name, shifted);
    }

    if (use_apple) {
        return emit_masked_key_sequence(&event, shifted ? symbol->apple_upper_1
                                                        : symbol->apple_lower_1,
                                        shifted ? symbol->apple_upper_2 : symbol->apple_lower_2);
    }

    return invoke_unicode_symbol(&event, symbol->lower, symbol->upper);
}

static int on_text_symbol_released(struct zmk_behavior_binding *binding,
                                   struct zmk_behavior_binding_event event) {
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api behavior_toucan_text_symbol_driver_api = {
    .binding_pressed = on_text_symbol_pressed,
    .binding_released = on_text_symbol_released,
};

BEHAVIOR_DT_INST_DEFINE(0, NULL, NULL, NULL, NULL, POST_KERNEL,
                        CONFIG_KERNEL_INIT_PRIORITY_DEFAULT,
                        &behavior_toucan_text_symbol_driver_api);

#endif /* DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT) */
