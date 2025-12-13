from abc import ABC, abstractmethod
from typing import Any, Dict


class IConfigurationSection(ABC):
    """Represents a section of configuration."""

    @abstractmethod
    def get_value(self, key: str, default_value: Any = None) -> Any:
        """Get a value from this configuration section with its original type."""
        pass

    @abstractmethod
    def get_section(self, key: str) -> "IConfigurationSection":
        """Get a subsection of this configuration section."""
        pass

    @abstractmethod
    def get_children(self) -> Dict[str, "IConfigurationSection"]:
        """Get all child sections."""
        pass

    @abstractmethod
    def exists(self) -> bool:
        """Check if this section has any data."""
        pass
