"""提示词加载与渲染工具。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


class PromptNotFoundError(KeyError):
    pass


@dataclass
class PromptRepository:
    """负责加载 prompts/ 目录下的所有提示词。"""

    base_dir: Path
    _cache: Dict[str, str] = None

    def __post_init__(self) -> None:
        self.base_dir = self.base_dir.resolve()
        self._cache = {}

    def _normalise_name(self, path: Path) -> str:
        return path.stem

    def load(self) -> None:
        if self._cache:
            return
        for file in self.base_dir.glob("*.md"):
            name = self._normalise_name(file)
            self._cache[name] = file.read_text(encoding="utf-8")

    def list_prompts(self) -> Iterable[str]:
        self.load()
        return sorted(self._cache.keys())

    def get(self, name: str) -> str:
        self.load()
        key = name if name in self._cache else name.replace(".md", "")
        if key not in self._cache:
            raise PromptNotFoundError(name)
        return self._cache[key]

    def render(self, name: str, **kwargs) -> str:
        template = self.get(name)
        if "{len(speaker_order)}" in template:
            template = template.replace("{len(speaker_order)}", "{speaker_order_len}")
            kwargs = {**kwargs, "speaker_order_len": len(kwargs.get("speaker_order", []) or [])}
        return template.format(**kwargs)


