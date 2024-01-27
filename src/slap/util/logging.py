""" Provides a logging formatter that understands color hints in the message and decorates it with """

from __future__ import annotations

import logging

import typing_extensions as te

from slap.util.notset import NotSet
from slap.util.terminal import StyleManager


def get_default_styles() -> StyleManager:
    manager = StyleManager()
    manager.add_style("info", "blue")
    manager.add_style("warning", "magenta")
    manager.add_style("error", "red")
    manager.add_style("critical", "bright red", None, "bold,underline")
    return manager


class TerminalColorFormatter(logging.Formatter):
    """A formatter that enhances text decorated with HTML-style tags with ANSI terminal colors. It can also be
    configured to eliminate the HTML tags instead of converting them to terminal styles."""

    def __init__(self, fmt: str, styles: StyleManager | None | NotSet = NotSet.Value) -> None:
        super().__init__(fmt)
        self.styles = get_default_styles() if styles is NotSet.Value else styles

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        if self.styles is None:
            return StyleManager.strip_tags(message)
        else:
            return self.styles.format(message, True)

    def install(self, target: te.Literal["tty", "notty"] | None = None) -> None:
        """Install the formatter on stream handlers on all handlers of the root logger that are attached to a TTY,
        or otherwise on all that are not attached to a TTY based on the *target* value. If no value is specified, it
        will install into TTY-attached stream handlers if #styles is set."""

        if target is None:
            target = "notty" if self.styles is None else "tty"

        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream.isatty():
                if target == "tty":
                    handler.setFormatter(self)
            elif target == "notty":
                handler.setFormatter(self)
