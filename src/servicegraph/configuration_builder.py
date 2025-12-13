import json
import os
from pathlib import Path
from typing import Any, Dict, List, Union

from .configuration import Configuration
from .i_configuration import IConfiguration
from .i_configuration_builder import IConfigurationBuilder


class ConfigurationBuilder(IConfigurationBuilder):
    """Builder for creating configuration."""

    def __init__(self) -> None:
        self._sources: List[Dict[str, Any]] = []

    def add_json_file(
        self, path: Union[str, Path], optional: bool = False
    ) -> "ConfigurationBuilder":
        """Add JSON file to configuration sources."""
        file_path = Path(path)

        if not file_path.is_absolute():
            # Resolve relative to current working directory
            file_path = Path.cwd() / file_path

        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._sources.append(data)
            elif not optional:
                raise FileNotFoundError(f"Configuration file not found: {file_path}")
        except json.JSONDecodeError as e:
            if not optional:
                raise ValueError(f"Invalid JSON in configuration file {file_path}: {e}")

        return self

    def add_environment_variables(self, prefix: str = "") -> "ConfigurationBuilder":
        """Add environment variables to configuration."""
        env_data: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if not prefix or key.startswith(prefix):
                # Remove prefix if specified
                config_key = key[len(prefix) :] if prefix else key

                # Convert environment variable format to nested structure
                # e.g., "DATABASE__CONNECTION_STRING" becomes {"DATABASE": {"CONNECTION_STRING": value}}
                if "__" in config_key:
                    self._set_nested_value(
                        env_data, config_key.replace("__", ":"), value
                    )
                else:
                    env_data[config_key] = value

        if env_data:
            self._sources.append(env_data)

        return self

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: str) -> None:
        """Set nested value using colon notation."""
        keys = key.split(":")
        current = data

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def build(self) -> IConfiguration:
        """Build the final configuration by merging all sources."""
        merged_data: Dict[str, Any] = {}

        # Merge all sources (later sources override earlier ones)
        for source in self._sources:
            self._deep_merge(merged_data, source)

        return Configuration(merged_data)

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source into target with case-insensitive key matching."""
        for key, value in source.items():
            # Find existing key with case-insensitive match
            matching_key = None
            for target_key in target.keys():
                if target_key.lower() == key.lower():
                    matching_key = target_key
                    break

            if (
                matching_key
                and isinstance(target[matching_key], dict)
                and isinstance(value, dict)
            ):
                # Both are dicts, merge recursively using the existing key
                self._deep_merge(target[matching_key], value)
            elif matching_key:
                # Key exists but not both dicts, override using the existing key
                target[matching_key] = value
            else:
                # New key, add it
                target[key] = value
