import os
from pathlib import Path
from typing import Any, Dict
import yaml


def find_project_root() -> Path:
    """Finds the root directory containing pyproject.toml or config folder."""
    curr = Path(__file__).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / "pyproject.toml").exists() or (parent / "config").exists():
            return parent
    return Path.cwd()


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """Safely loads a YAML file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class ConfigManager:
    """Centralized configuration manager loading YAML configs."""
    _instance = None

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            self.root_dir = find_project_root()
            self.config_dir = self.root_dir / "config"
        else:
            self.config_dir = Path(config_dir)
            self.root_dir = self.config_dir.parent

        self.markets = load_yaml(self.config_dir / "markets.yaml")
        self.storage = load_yaml(self.config_dir / "storage.yaml")
        self.app = load_yaml(self.config_dir / "app.yaml")

    def get_market_config(self, market_name: str) -> Dict[str, Any]:
        """Retrieves market configuration by name."""
        markets = self.markets.get("markets", {})
        if market_name not in markets:
            raise KeyError(f"Market '{market_name}' not configured in markets.yaml")
        return markets[market_name]

    def get_storage_config(self) -> Dict[str, Any]:
        """Retrieves battery storage configuration."""
        return self.storage.get("storage", {})

    def get_benchmark_config(self) -> Dict[str, Any]:
        """Retrieves benchmark strategy configuration."""
        return self.storage.get("benchmark", {})

    def get_path(self, path_key: str) -> Path:
        """Resolves project relative paths to absolute Path instances."""
        rel_path = self.app.get("paths", {}).get(path_key)
        if not rel_path:
            raise KeyError(f"Path key '{path_key}' not found in app.yaml")
        return self.root_dir / rel_path


# Global default configuration instance
def get_config(config_dir: Path | None = None) -> ConfigManager:
    return ConfigManager(config_dir)
