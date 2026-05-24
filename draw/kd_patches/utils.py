"""Module containing lower-level SVG drawing utils, to be used as a mixin."""

import re
import string
from html import escape
from io import StringIO
from textwrap import TextWrapper
from typing import Literal, Sequence

# `{{class:NAME}}` prefix on any legend field is stripped at draw time and
# `NAME` is added to the rendered element's class list. Lets a single
# corner/side field (e.g. `left`) host entries styled in different colours,
# which LayoutKey's plain-string corner fields otherwise can't express.
_CLASS_PREFIX_RE = re.compile(r"^\{\{class:([A-Za-z0-9_-]+)\}\}")


def _extract_class_prefix(text: str) -> tuple[str | None, str]:
    if m := _CLASS_PREFIX_RE.match(text):
        return m.group(1), text[m.end():]
    return None, text

from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.glyph import GlyphMixin
from keymap_drawer.physical_layout import Point

LegendType = Literal["tap", "hold", "shifted", "left", "right", "tl", "tr", "bl", "br"]


class UtilsMixin(GlyphMixin):
    """Mixin that adds low-level SVG drawing methods for KeymapDrawer."""

    # initialized in KeymapDrawer
    cfg: DrawConfig
    layer_names: set[str]
    out: StringIO

    @staticmethod
    def _str_to_id(val: str) -> str:
        if not val:
            return "o_o"
        val = val.replace(" ", "-")
        while val[0] not in string.ascii_letters:
            val = val[1:]
            if not val:
                return "x_x"
        allowed = string.ascii_letters + string.digits + "-_:."
        return "".join([c for c in val if c in allowed])

    @staticmethod
    def _to_class_str(classes: Sequence[str]) -> str:
        return (' class="' + " ".join(c for c in classes if c) + '"') if classes else ""

    def _split_text(self, text: str, truncate: int = 0, line_width: int = 0) -> list[str]:
        # Strip class prefix before splitting so its length doesn't trigger word-wrapping.
        # _draw_legend re-extracts it from words[0].
        extra_class, text = _extract_class_prefix(text)

        if self.legend_is_glyph(text):
            lines = [text]
        else:
            # do not split on double spaces, but do split on single
            lines = [word.replace("\x00", " ") for word in text.replace("  ", "\x00").split()]

            # wrap on word boundaries if a line is too long
            if line_width > 0 and len(lines) < truncate:
                tw = TextWrapper(width=line_width, break_long_words=False, break_on_hyphens=False)

                wrapped: list[str] = []
                for i, line in enumerate(lines):
                    if len(line) > line_width:
                        wrapped_line = tw._wrap_chunks(re.split(r"(?<!^.)\b", line))  # pylint: disable=protected-access

                        # if we are going to exceed the max line limit, give up here and do not modify lines
                        new_total_lines = len(wrapped) + len(wrapped_line) - 1 + len(lines) - i
                        if (diff := new_total_lines - truncate) > 0:
                            if diff < len(wrapped_line):  # salvage part of this line as much as we can
                                wrapped += wrapped_line[: -diff - 1] + ["".join(wrapped_line[-diff - 1 :])]
                            else:
                                wrapped.append(line)
                            wrapped += lines[i + 1 :]
                            break
                        wrapped += wrapped_line
                    else:
                        wrapped.append(line)
                lines = wrapped

            # truncate number of lines if requested
            if truncate and len(lines) > truncate:
                lines = lines[: truncate - 1] + ["…"]

        if extra_class is not None and lines:
            lines[0] = f"{{{{class:{extra_class}}}}}{lines[0]}"
        return lines

    def _draw_rect(self, p: Point, dims: Point, radii: Point, classes: Sequence[str]) -> None:
        self.out.write(
            f'<rect rx="{round(radii.x)}" ry="{round(radii.y)}"'
            f' x="{round(p.x - dims.x / 2)}" y="{round(p.y - dims.y / 2)}" '
            f'width="{round(dims.x)}" height="{round(dims.y)}"{self._to_class_str(classes)}/>\n'
        )

    def _draw_key(self, dims: Point, classes: Sequence[str]) -> None:
        if self.cfg.draw_key_sides:
            # draw side rectangle
            self._draw_rect(
                Point(0.0, 0.0),
                dims,
                Point(self.cfg.key_rx, self.cfg.key_ry),
                classes=[*classes, "side"],
            )
            # draw internal rectangle
            self._draw_rect(
                Point(-self.cfg.key_side_pars.rel_x, -self.cfg.key_side_pars.rel_y),
                dims - Point(self.cfg.key_side_pars.rel_w, self.cfg.key_side_pars.rel_h),
                Point(self.cfg.key_side_pars.rx, self.cfg.key_side_pars.ry),
                classes=classes,
            )
        else:
            # default key style
            self._draw_rect(
                Point(0.0, 0.0),
                dims,
                Point(self.cfg.key_rx, self.cfg.key_ry),
                classes=classes,
            )

    def _get_scaling(self, width: int) -> str:
        if not self.cfg.shrink_wide_legends or width <= self.cfg.shrink_wide_legends:
            return ""
        return f' style="font-size: {max(60.0, 100 * self.cfg.shrink_wide_legends / width):.0f}%"'

    def _truncate_word(self, word: str) -> str:
        if not self.cfg.shrink_wide_legends or len(word) <= (limit := int(1.7 * self.cfg.shrink_wide_legends)):
            return word
        return word[: limit - 1] + "…"

    def _draw_text(self, p: Point, word: str, classes: Sequence[str]) -> None:
        if not word:
            return
        word = self._truncate_word(word)
        self.out.write(f'<text x="{round(p.x)}" y="{round(p.y)}"{self._to_class_str(classes)}>')
        self.out.write(
            f"<tspan{scale}>{escape(word)}</tspan>" if (scale := self._get_scaling(len(word))) else escape(word)
        )
        self.out.write("</text>\n")

    def _draw_textblock(self, p: Point, words: Sequence[str], classes: Sequence[str], shift: float = 0) -> None:
        words = [self._truncate_word(word) for word in words]
        self.out.write(f'<text x="{round(p.x)}" y="{round(p.y)}"{self._to_class_str(classes)}>\n')
        dy_0 = (len(words) - 1) * (self.cfg.line_spacing * (1 + shift / 2) / 2)
        scaling = self._get_scaling(max(len(w) for w in words))
        self.out.write(f'<tspan x="{round(p.x)}" dy="-{round(dy_0, 2)}em"{scaling}>{escape(words[0])}</tspan>')
        for word in words[1:]:
            self.out.write(f'<tspan x="{round(p.x)}" dy="{self.cfg.line_spacing}em"{scaling}>{escape(word)}</tspan>')
        self.out.write("\n</text>\n")

    def _draw_glyph(self, p: Point, name: str, legend_type: LegendType, classes: Sequence[str]) -> None:
        width, height, d_x, d_y = self.get_glyph_dimensions(name, legend_type)

        classes = [*classes, "glyph", name]
        self.out.write(
            f'<use href="#{name}" xlink:href="#{name}" x="{round(p.x - d_x)}" y="{round(p.y - d_y)}" '
            f'height="{height}" width="{width}"{self._to_class_str(classes)}/>\n'
        )

    def _draw_legend(
        self, p: Point, words: Sequence[str], classes: Sequence[str], legend_type: LegendType, shift: float = 0
    ) -> None:
        if not words:
            return

        # Strip optional `{{class:NAME}}` prefix from the first word and
        # promote NAME into the rendered element's class list.
        extra_class = None
        if words:
            extra_class, stripped = _extract_class_prefix(words[0])
            if extra_class is not None:
                words = [stripped, *words[1:]]

        is_layer = self.cfg.style_layer_activators and (layer_name := " ".join(words)) in self.layer_names

        classes = [*classes, legend_type]
        if extra_class:
            classes.append(extra_class)
        if is_layer:
            classes.append("layer-activator")

        if len(words) == 1:
            if glyph := self.legend_is_glyph(words[0]):
                self._draw_glyph(p, glyph, legend_type, classes)
                return
            # Handle "$$glyph$$suffix" mixed pattern (e.g. $$mdi:bluetooth$$1).
            # We fix three gotchas:
            #  1. text-anchor defaults to middle, which shifts the suffix back
            #     over the glyph. Force text-anchor:start so it sits cleanly
            #     after the glyph.
            #  2. MDI icons carry ~15-20% empty viewBox padding on each side,
            #     so the reported `width` overstates the visible glyph. Use a
            #     negative gap to tuck the suffix into that padding.
            #  3. For edge-anchored legend types (left/right), the pair still
            #     ends up biased toward the centre because the anchor p sits
            #     `small_pad` pixels inside the key edge. Nudge the glyph
            #     further toward the edge so the combined label sits tight
            #     against it.
            if (pfx := self.legend_glyph_prefix(words[0])) is not None:
                glyph_name, suffix = pfx
                width, _h, _dx, _dy = self.get_glyph_dimensions(glyph_name, legend_type)
                edge_shift = -(self.cfg.small_pad - 1) if legend_type == "left" else (
                    (self.cfg.small_pad - 1) if legend_type == "right" else 0
                )
                glyph_p = Point(p.x + edge_shift, p.y)
                self._draw_glyph(glyph_p, glyph_name, legend_type, classes)
                # gap = -width*0.3 overlaps the glyph's empty side padding
                # without eating into its visible shape
                gap = -width * 0.3
                text_x = round(glyph_p.x + width + gap)
                self.out.write(
                    f'<text x="{text_x}" y="{round(p.y)}" style="text-anchor:start"'
                    f'{self._to_class_str(classes)}>{escape(suffix)}</text>\n'
                )
                return

        if is_layer:
            self.out.write(f'<a href="#{self._str_to_id(layer_name)}">\n')

        if len(words) == 1:
            self._draw_text(p, words[0], classes)
        else:
            self._draw_textblock(p, words, classes, shift)

        if is_layer:
            self.out.write("</a>")
