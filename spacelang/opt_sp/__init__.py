"""Browser-based visual debugger for SpaceLang."""

from ..web_bridge import trace_program
from .server import open_browser, server

__version__ = "0.1.5"

__all__ = ["server", "open_browser", "trace_program", "__version__"]
