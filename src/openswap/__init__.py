"""OpenSwap: OpenSoft menu bar app for rotating AI coding accounts."""

from importlib.metadata import version

__version__ = version("openswap")

from openswap.engine import Engine
from openswap.switcher import ClaudeAccountSwitcher

__all__ = ["Engine", "ClaudeAccountSwitcher", "__version__"]
