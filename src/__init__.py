"""
IMA Copilot MCP 服务器

基于 fastmcp v2 框架的腾讯 IMA Copilot MCP (Model Context Protocol) 服务器。
"""

__version__ = "0.1.0"
__author__ = "IMA MCP Team"
__description__ = "MCP server for Tencent IMA Copilot functionality"

from .main import main
from .mcp_server import get_mcp_server
from .config import get_config, get_app_config

__all__ = [
    "main",
    "get_mcp_server",
    "get_config",
    "get_app_config",
    "__version__",
    "__author__",
    "__description__"
]