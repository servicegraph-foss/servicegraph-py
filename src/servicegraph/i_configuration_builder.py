from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .i_configuration import IConfiguration


class IConfigurationBuilder(ABC):
    """Builder pattern for configuration setup."""

    @abstractmethod
    def add_json_file(
        self, path: Union[str, Path], optional: bool = False
    ) -> "IConfigurationBuilder":
        """Add a JSON configuration file."""
        pass

    @abstractmethod
    def add_environment_variables(self, prefix: str = "") -> "IConfigurationBuilder":
        """Add environment variables with optional prefix."""
        pass

    @abstractmethod
    def build(self) -> "IConfiguration":
        """Build the configuration."""
        pass
