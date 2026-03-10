from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Dict

@dataclass
class PromptStore:
    root: Path
    _cache: Dict[str, str]

    @classmethod
    def from_project_root(cls, project_root: str) -> "PromptStore":
        return cls(root=Path(project_root), _cache={})

    def load(self, rel_path: str) -> str:
        if rel_path in self._cache:
            return self._cache[rel_path]
        text = (self.root / rel_path).read_text(encoding="utf-8")
        self._cache[rel_path] = text
        return text

    def render(self, rel_path: str, **vars) -> str:
        text = self.load(rel_path)
        return Template(text).safe_substitute(**vars)
