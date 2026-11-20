"""Browser-based visual debugger for SpaceLang."""

from ..web_bridge import trace_program
from .llm_proxy import LLMConfig
from .server import open_browser, server

__version__ = "0.2.0"

__all__ = ["server", "open_browser", "trace_program", "LLMConfig", "__version__"]
