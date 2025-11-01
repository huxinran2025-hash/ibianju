"""狼人杀命令行引擎模块。"""

from .cli import run_cli
from .web import run_server

__all__ = ["run_cli", "run_server"]


