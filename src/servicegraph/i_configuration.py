from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Type, TypeVar

if TYPE_CHECKING:
    from .i_configuration_section import IConfigurationSection

T = TypeVar("T")


class IConfiguration(ABC):
    """Configuration interface similar to C# IConfiguration."""

    @abstractmethod
    def get_value(self, key: str, default_value: Any = None) -> Any:
        """Get a configuration value by key using colon notation (e.g., 'Section:SubSection:Key').

        Returns the value with its original type (str, int, bool, float, dict, list, etc.).
        """
        pass

    @abstractmethod
    def get_section(self, key: str) -> "IConfigurationSection":
        """Get a configuration section."""
        pass

    @abstractmethod
    def bind(self, instance: object, key: str = "") -> None:
        """Bind configuration values to an object instance."""
        pass

    @abstractmethod
    def get(self, type_class: Type[T], key: str = "") -> T:
        """Get a strongly-typed configuration object."""
        pass
