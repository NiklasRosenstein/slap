from __future__ import annotations

import abc
import dataclasses
import enum
import re
import typing as t


class Attribute(enum.Enum):
    RESET = 0
    BOLD = 1
    FAINT = 2
    ITALIC = 3
    UNDERLINE = 4
    SLOW_BLINK = 5
    RAPID_BLINK = 6
    REVERSE_VIDEO = 7
    CONCEAL = 8
    CROSSED_OUT = 9
    FONT_0 = 10
    FONT_1 = 11
    FONT_2 = 12
    FONT_3 = 13
    FONT_4 = 14
    FONT_5 = 15
    FONT_6 = 16
    FONT_7 = 17
    FONT_8 = 18
    FONT_9 = 19
    FRAKTUR = 20
    DOUBLY_UNDERLINE = 21
    NORMAL_INTENSITY = 22
    NOT_ITALIC = 23
    UNDERLINE_OFF = 24
    BLINK_OFF = 25
    REVERSE_OFF = 27
    REVEAL = 28
    CROSSED_OUT_OFF = 29
    FRAMED = 51
    ENCIRCLED = 52
    OVERLINED = 53
    FRAMED_OFF = 54
    OVERLINED_OFF = 55


class Color(abc.ABC):
    @abc.abstractmethod
    def as_foreground(self) -> str: ...

    @abc.abstractmethod
    def as_background(self) -> str: ...


class SgrColorName(enum.Enum):
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7
    GRAY = 8
    DEFAULT = 9


@dataclasses.dataclass
class SgrColor(Color):
    """Represents a color from the SGR space (see #SgrColorName)."""

    name: SgrColorName
    bright: bool

    def __init__(self, name: SgrColorName, bright: bool = False) -> None:
        if isinstance(name, str):
            name = SgrColorName[name.upper()]
        self.name = name
        self.bright = bright

    def as_foreground(self) -> str:
        return str((90 if self.bright else 30) + self.name.value)

    def as_background(self) -> str:
        return str((100 if self.bright else 40) + self.name.value)


@dataclasses.dataclass
class LutColor(Color):
    """Represents a LUT color, which is one of 216 colors."""

    index: int

    def as_foreground(self) -> str:
        return "38;5;" + str(self.index)

    def as_background(self) -> str:
        return "48;5;" + str(self.index)

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> "LutColor":
        """
        Given RGB values in the range of [0..5], returns a #LutColor pointing
        to the color index that resembles the specified color coordinates.
        """

        def _check_range(name, value):
            if not (0 <= value < 6):
                raise ValueError('bad value for parameter "{}": {} ∉ [0..5]'.format(name, value))

        _check_range("r", r)
        _check_range("g", g)
        _check_range("b", b)

        return cls((16 + 36 * r) + (6 * g) + b)


class TrueColor(Color):
    """Represents a true color comprised of three color components."""

    r: int
    g: int
    b: int

    def as_foreground(self) -> str:
        return "38;2;{};{};{}".format(self.r, self.g, self.b)

    def as_background(self) -> str:
        return "48;2;{};{};{}".format(self.r, self.g, self.b)


def parse_color(color_string: str) -> Color:
    """Parses a color string of one of the following formats and returns a corresponding #SgrColor, #LutColor or
    #TrueColor.

    * `<color_name>`, `BRIGHT_<color_name>`: #SgrColor (case insensitive, underline optional)
    * `%rgb`, `$xxx`: #LutColor
    * `#cef`, `#cceeff`: #TrueColor
    """

    if color_string.startswith("%") and len(color_string) == 4:
        try:
            r, g, b = map(int, color_string[1:])
        except ValueError:
            pass
        else:
            if r < 6 and g < 6 and b < 6:
                return LutColor.from_rgb(r, g, b)

    elif color_string.startswith("$") and len(color_string) <= 4:
        try:
            index = int(color_string[1:])
        except ValueError:
            pass
        else:
            if index >= 0 and index < 256:
                return LutColor(index)

    elif color_string.startswith("#") and len(color_string) in (4, 7):
        parts = re.findall("." if len(color_string) == 4 else "..", color_string[1:])
        if len(color_string) == 4:
            parts = [x * 2 for x in parts]
        try:
            parts = [int(x, 16) for x in parts]
        except ValueError:
            pass
        else:
            return TrueColor(*parts)

    else:
        color_string = color_string.upper()
        bright = color_string.startswith("BRIGHT_") or color_string.startswith("BRIGHT ")
        if bright:
            color_string = color_string[7:]
        if hasattr(SgrColorName, color_string):
            return SgrColor(SgrColorName[color_string], bright)

    raise ValueError("unrecognizable color string: {!r}".format(color_string))


@dataclasses.dataclass
class Style:
    """A style is a combination of foreground and background color, as well as a list of attributes."""

    RESET: t.ClassVar[Style]

    fg: Color | None = None
    bg: Color | None = None
    attrs: list[Attribute] | None = None

    def __init__(
        self,
        fg: Color | str | None = None,
        bg: Color | str | None = None,
        attrs: t.Sequence[Attribute | str] | str | None = None,
    ) -> None:
        """The constructor allows you to specify all arguments also as strings. The foreground and background are parsed
        with #parse_color(). The *attrs* can be a comma-separated string."""

        if isinstance(fg, str):
            fg = parse_color(fg)
        if isinstance(bg, str):
            bg = parse_color(bg)
        if isinstance(attrs, str):
            attrs = [x.strip() for x in attrs.split(",") if x.strip()]
        self.fg = fg
        self.bg = bg
        if attrs is None:
            self.attrs = None
        else:
            self.attrs = []
            for attr in attrs:
                if isinstance(attr, str):
                    self.attrs.append(Attribute[attr.upper()])
                else:
                    self.attrs.append(attr)

    def to_escape_sequence(self) -> str:
        seq = []
        if self.fg:
            seq.append(self.fg.as_foreground())
        if self.bg:
            seq.append(self.bg.as_background())
        seq.extend(str(attr.value) for attr in self.attrs or ())
        return "\033[" + ";".join(seq) + "m"


Style.RESET = Style(attrs="reset")


class StyleManager:
    """Allows you to register styles and format text using HTML-style tags."""

    TAG_EXPR = r"<([^>=]+)([^>]*)>(.*?)</\1>"

    def __init__(self) -> None:
        self._styles: dict[str, Style] = {}

    def add_style(
        self,
        name: str,
        fg: Color | str | None = None,
        bg: Color | str | None = None,
        attrs: list[Attribute | str] | str | None = None,
    ) -> None:
        self._styles[name] = Style(fg, bg, attrs)

    def parse_style(self, style_string: str, safe: bool = False) -> Style:
        """Parses a style string that is valid inside an opening HTML-style tag accepted in strings by #format()."""

        parts = style_string.split(";")
        style: Style = Style()
        for part in parts:
            try:
                if part.startswith("fg="):
                    style = Style(parse_color(part[3:]), style.bg, style.attrs)
                elif part.startswith("bg="):
                    style = Style(style.fg, parse_color(part[3:]), style.attrs)
                elif part.startswith("attr="):
                    style = Style(style.fg, style.bg, (style.attrs or []) + [Attribute[part[5:].upper()]])
                else:
                    style = self._styles[part]
            except (ValueError, KeyError):
                if not safe:
                    raise

        return style

    def format(self, text: str, safe: bool = False, repl: t.Callable[[str, str], str] | None = None) -> str:
        """Formats text that contains HTML-style tags that represent styles in the style manager. In addition, special
        tags `<fg={color}>`, `<bg={color}>` or <attr={attrs}>` can be used to manually specify the exact styling of the
        text and the can be combined (such as `<bg=bright red;attr=underline>`). If *safe* is set to `True`, tags
        referencing styles that are unknown to the manager are ignored."""

        def _regex_sub(m: re.Match) -> str:
            style_string = m.group(1) + m.group(2)
            content = m.group(3)
            if repl is None:
                style = self.parse_style(style_string, safe)
                return style.to_escape_sequence() + content + Style.RESET.to_escape_sequence()
            else:
                return repl(style_string, content)

        upper_limit = 15
        prev_text = text
        for _ in range(upper_limit):
            text = re.sub(self.TAG_EXPR, _regex_sub, text, flags=re.S | re.M)
            if prev_text == text:
                break
            prev_text = text

        return prev_text

    @classmethod
    def strip_tags(cls, text: str) -> str:
        return cls().format(text, True, lambda _, s: s)
