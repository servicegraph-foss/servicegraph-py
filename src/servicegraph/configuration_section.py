from typing import Any, Dict

from .i_configuration_section import IConfigurationSection


class ConfigurationSection(IConfigurationSection):
    """Implementation of configuration section."""

    def __init__(self, data: Dict[str, Any], path: str = ""):
        self._data = data if data is not None else {}
        self._path = path

    def get_value(self, key: str, default_value: Any = None) -> Any:
        """Get value from this section with its original type."""
        # Case-insensitive key lookup
        matching_key = None
        for dict_key in self._data.keys():
            if dict_key.lower() == key.lower():
                matching_key = dict_key
                break

        if matching_key:
            value = self._data[matching_key]
            return value if value is not None else default_value
        return default_value

    def get_section(self, key: str) -> IConfigurationSection:
        """Get a subsection."""
        if key in self._data and isinstance(self._data[key], dict):
            section_path = f"{self._path}:{key}" if self._path else key
            return ConfigurationSection(self._data[key], section_path)
        return ConfigurationSection({}, f"{self._path}:{key}" if self._path else key)

    def get_children(self) -> Dict[str, IConfigurationSection]:
        """Get all child sections."""
        children: Dict[str, IConfigurationSection] = {}
        for key, value in self._data.items():
            if isinstance(value, dict):
                section_path = f"{self._path}:{key}" if self._path else key
                children[key] = ConfigurationSection(value, section_path)
        return children

    def exists(self) -> bool:
        """Check if this section has any data."""
        return bool(self._data)
