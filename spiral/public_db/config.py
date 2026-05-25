"""Configuration for the Public Literature Database."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MergePolicyConfig:
    merge_limitations: bool = True
    inherit_credibility: bool = True
    inherit_tags: bool = True
    inherit_verification: bool = True
    inherit_code_url: bool = True
    max_limitations: int = 50

    def to_dict(self) -> dict[str, Any]:
        return {
            "merge_limitations": self.merge_limitations,
            "inherit_credibility": self.inherit_credibility,
            "inherit_tags": self.inherit_tags,
            "inherit_verification": self.inherit_verification,
            "inherit_code_url": self.inherit_code_url,
            "max_limitations": self.max_limitations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergePolicyConfig:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DBConfig:
    """Runtime configuration for the public literature database."""

    enabled: bool = True
    db_path: str = ""
    min_hit_threshold: int = 10
    query_cache_ttl_days: int = 180
    auto_tagging: bool = True
    default_limit: int = 50
    max_limit: int = 500
    timeout: float = 30.0
    merge_policy: MergePolicyConfig = field(default_factory=MergePolicyConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> DBConfig:
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            return cls.default()

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        cfg = raw.get("public_literature_db", {})
        merge_raw = cfg.get("merge_policy", {})
        return cls(
            enabled=cfg.get("enabled", True),
            db_path=cfg.get("path", ""),
            min_hit_threshold=cfg.get("min_hit_threshold", 10),
            query_cache_ttl_days=cfg.get("query_cache_ttl_days", 180),
            auto_tagging=cfg.get("auto_tagging", True),
            default_limit=cfg.get("default_limit", 50),
            max_limit=cfg.get("max_limit", 500),
            timeout=cfg.get("timeout", 30.0),
            merge_policy=MergePolicyConfig.from_dict(merge_raw),
        )

    @classmethod
    def default(cls) -> DBConfig:
        """Return default configuration with auto-resolved db_path.

        Resolution order:
            1. SPIRAL_FRAMEWORK_ROOT env var (if set)
            2. Auto-detect from spiral/__file__ location
            3. Fallback to ~/.autopaper2/
        """
        framework_root = ""
        # 1. Environment override
        env_root = os.environ.get("SPIRAL_FRAMEWORK_ROOT", "")
        if env_root:
            framework_root = env_root
        else:
            # 2. Auto-detect from package location
            try:
                import spiral
                pkg_file = getattr(spiral, "__file__", None)
                if pkg_file:
                    framework_root = str(Path(pkg_file).parent.parent.resolve())
            except Exception:
                pass

        if framework_root:
            db_path = str(
                Path(framework_root) / "data" / "public_literature_db" / "literature.db"
            )
        else:
            # 3. Final fallback
            db_path = str(Path.home() / ".autopaper2" / "public_literature.db")

        return cls(db_path=db_path)

    @classmethod
    def from_project(cls, project_root: str | Path) -> DBConfig:
        """Load config from a project's config/public_db.yaml if it exists,
        otherwise use framework-wide defaults."""
        project_cfg = Path(project_root) / "config" / "public_db.yaml"
        if project_cfg.exists():
            return cls.from_yaml(project_cfg)
        return cls.default()

    def to_yaml(self) -> str:
        """Serialize configuration to YAML string."""
        data = {
            "public_literature_db": {
                "enabled": self.enabled,
                "path": self.db_path,
                "min_hit_threshold": self.min_hit_threshold,
                "query_cache_ttl_days": self.query_cache_ttl_days,
                "auto_tagging": self.auto_tagging,
                "default_limit": self.default_limit,
                "max_limit": self.max_limit,
                "timeout": self.timeout,
                "merge_policy": self.merge_policy.to_dict(),
            }
        }
        return yaml.dump(data, allow_unicode=True, sort_keys=False)
