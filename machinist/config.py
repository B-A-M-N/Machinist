from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence


DEFAULT_IGNORE_GLOBS: List[str] = [
    ".env",
    ".env*",
    "*.key",
    "id_rsa*",
    "*.pem",
    "*.pfx",
    "*.p12",
    "*.sqlite",
    "*.db",
]


@dataclass
class MachinistConfig:
    """
    Central configuration for sandboxing and exploration.
    Defaults are conservative: stay inside the current workspace and ignore common secrets.
    """

    workspace: Path = field(default_factory=lambda: Path(os.getcwd()))
    exploration_paths: List[Path] = field(default_factory=lambda: [Path(os.getcwd())])
    exploration_file_types: Sequence[str] = (".py", ".csv", ".json", ".txt", ".xml")
    exploration_ignore_globs: List[str] = field(default_factory=lambda: list(DEFAULT_IGNORE_GLOBS))
    max_exploration_depth: int = 2
    enable_exploration: bool = True

    allow_network: bool = False
    coverage_threshold: float = 0.6

    # LLM Configuration
    models: List[str] = field(default_factory=list)
    spec_model_name: str | None = "rnj-1:8b-cloud"
    impl_model_name: str | None = None
    test_model_name: str | None = "rnj-1:8b-cloud"

    def resolved_paths(self) -> List[Path]:
        return [p.resolve() for p in self.exploration_paths]
