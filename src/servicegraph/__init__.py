"""
servicegraph - A lightweight dependency injection framework for Python

This package provides a simple yet powerful dependency injection container
with support for service lifetimes, configuration management, and type safety.
"""

__version__ = "0.1.0"
__author__ = "ServiceGraph Contributors"
__license__ = "See LICENSE file"

# Application and context
from .application_builder import ApplicationBuilder
from .configuration import Configuration
from .configuration_builder import ConfigurationBuilder
from .configuration_section import ConfigurationSection
from .dependency_injection_utils import *

# Configuration management
from .i_configuration import IConfiguration
from .i_configuration_builder import IConfigurationBuilder
from .i_configuration_section import IConfigurationSection
from .request_context import RequestContext

# Core dependency injection components
from .service_collection import ServiceCollection
from .service_lifetime import ServiceLifetime
from .service_locator import get_named_service, get_service
from .service_provider import ServiceProvider
from .service_registration import ServiceRegistration

# Type hints and utilities
from .type_hints import *

# Public API - only expose what users should directly interact with
__all__ = [
    # Version info
    "__version__",
    # Core DI classes
    "ServiceCollection",
    "ServiceProvider",
    "ServiceLifetime",
    "get_service",
    "get_named_service",
    # Configuration classes
    "Configuration",
    "ConfigurationBuilder",
    "ConfigurationSection",
    # Application setup
    "ApplicationBuilder",
    "RequestContext",
    # Abstract interfaces (for type hinting)
    "IConfiguration",
    "IConfigurationBuilder",
    "IConfigurationSection",
]

# Package metadata
__description__ = "A lightweight dependency injection framework for Python"
__url__ = "https://github.com/servicegraph-foss/servicegraph-py"
__maintainer__ = "servicegraph Contributors"
__maintainer_email__ = "servicegraph.contact@gmail.com"

# Minimum Python version requirement
import sys

if sys.version_info < (3, 8):
    raise ImportError(
        "servicegraph requires Python 3.8 or later. "
        f"You are using Python "
        f"{sys.version_info.major}.{sys.version_info.minor}."
    )

# Clean up module namespace
del sys
