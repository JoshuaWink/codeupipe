"""
DeployAdapter protocol and DeployTarget metadata.

All deploy adapters implement this ABC. Cloud-specific adapters live in
separate packages and register via entry points under 'codeupipe.deploy'.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["DeployTarget", "DeployAdapter"]


@dataclass
class DeployTarget:
    """Metadata about a deployment target."""
    name: str
    description: str
    requires: List[str] = field(default_factory=list)


class DeployAdapter(ABC):
    """Protocol for deployment adapters.

    Subclasses implement target(), validate(), generate(), and deploy().
    """

    @abstractmethod
    def target(self) -> DeployTarget:
        """Return metadata about this deploy target."""

    @abstractmethod
    def validate(self, pipeline_config: dict, **options) -> List[str]:
        """Pre-flight checks. Return list of issues (empty = OK)."""

    @abstractmethod
    def generate(self, pipeline_config: dict, output_dir: Path, **options) -> List[Path]:
        """Generate deployment artifacts (handler, infra, Dockerfile).

        Returns list of generated file paths.
        """

    @abstractmethod
    def deploy(self, output_dir: Path, *, dry_run: bool = False, **options) -> str:
        """Execute the deployment. Returns deployment URL or status message."""
