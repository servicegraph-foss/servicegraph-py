from dataclasses import fields, is_dataclass
from typing import Any, Dict, Type, TypeVar

from .configuration_section import ConfigurationSection
from .i_configuration import IConfiguration
from .i_configuration_section import IConfigurationSection

T = TypeVar("T")


class Configuration(IConfiguration):
    """Main configuration implementation."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def get_value(self, key: str, default_value: Any = None) -> Any:
        """Get value using colon notation (e.g., 'Database:ConnectionString').

        Returns the value with its original type (str, int, bool, float, etc.).
        """
        keys = key.split(":")
        current: Any = self._data

        for k in keys:
            if not isinstance(current, dict):
                return default_value

            # Case-insensitive key lookup
            matching_key = None
            for dict_key in current.keys():
                if dict_key.lower() == k.lower():
                    matching_key = dict_key
                    break

            if matching_key:
                current = current[matching_key]
            else:
                return default_value

        return current if current is not None else default_value

    def get_section(self, key: str) -> IConfigurationSection:
        """Get a configuration section."""
        keys = key.split(":")
        current: Any = self._data

        for k in keys:
            if not isinstance(current, dict):
                return ConfigurationSection({}, key)

            # Case-insensitive key lookup
            matching_key = None
            for dict_key in current.keys():
                if dict_key.lower() == k.lower():
                    matching_key = dict_key
                    break

            if matching_key:
                current = current[matching_key]
            else:
                return ConfigurationSection({}, key)

        if isinstance(current, dict):
            return ConfigurationSection(current, key)
        return ConfigurationSection({}, key)

    def remove_value(self, key: str) -> bool:
        """
        Remove a configuration value by key.

        :param key: Configuration key using colon notation
        :return: True if the key was found and removed, False otherwise
        """
        keys = key.split(":")
        current = self._data

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return False

        # Remove the final key
        if isinstance(current, dict) and keys[-1] in current:
            del current[keys[-1]]
            return True
        return False

    def clear(self) -> None:
        """Clear all configuration data."""
        self._data.clear()

    def update(self, data: Dict[str, Any]) -> None:
        """
        Update configuration with new data.

        :param data: Dictionary of configuration data to merge
        """
        self._deep_merge(self._data, data)

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

    def bind(self, instance: object, key: str = "") -> None:
        """Bind configuration to an object instance."""
        if key:
            section = self.get_section(key)
            data = section._data if hasattr(section, "_data") else {}
        else:
            data = self._data

        self._bind_to_instance(instance, data)

    def get(self, type_class: Type[T], key: str = "") -> T:
        """Get strongly-typed configuration object."""
        if key:
            section = self.get_section(key)
            data = section._data if hasattr(section, "_data") else {}
        else:
            data = self._data

        return self._create_typed_instance(type_class, data)

    def _bind_to_instance(self, instance: object, data: Dict[str, Any]) -> None:
        """Bind data to an existing object instance with case-insensitive matching."""
        for key, value in data.items():
            # Try exact match first
            if hasattr(instance, key):
                setattr(instance, key, value)
            else:
                # Try case-insensitive match
                key_lower = key.lower()
                for attr_name in dir(instance):
                    if not attr_name.startswith("_") and attr_name.lower() == key_lower:
                        setattr(instance, attr_name, value)
                        break

    def _create_typed_instance(self, type_class: Type[T], data: Dict[str, Any]) -> T:
        """Create a typed instance from configuration data."""
        if is_dataclass(type_class):
            # Handle dataclass
            field_values = {}
            for field in fields(type_class):
                if field.name in data:
                    field_values[field.name] = data[field.name]
            return type_class(**field_values)

        elif hasattr(type_class, "__annotations__"):
            # Handle typed class with annotations
            return type_class(**data)

        else:
            # Fallback - try direct instantiation
            try:
                return type_class(**data)
            except TypeError:
                # If direct instantiation fails, create empty instance and bind
                instance = type_class()
                self._bind_to_instance(instance, data)
                return instance
