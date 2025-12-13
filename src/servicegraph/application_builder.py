from typing import Any, Callable, Optional

from .configuration_builder import ConfigurationBuilder
from .i_configuration import IConfiguration
from .i_configuration_builder import IConfigurationBuilder
from .service_collection import ServiceCollection
from .service_provider import ServiceProvider


class ApplicationBuilder:
    def __init__(self, environment: Optional[str] = None) -> None:
        self.environment = environment
        self.services = ServiceCollection()
        self._middleware: list[Any] = []
        self._configuration: Optional[IConfiguration] = None
        self._config_builder: Optional[IConfigurationBuilder] = None

        # Always ensure a default configuration is available
        self._ensure_default_configuration()

    def _ensure_default_configuration(self) -> None:
        """Ensure a default empty configuration is always available."""
        if self._configuration is None:
            # Create a default empty configuration
            self._config_builder = ConfigurationBuilder()
            self._configuration = self._config_builder.build()
            self.services.add_instance(IConfiguration, self._configuration)

    def configure_configuration(
        self, config_action: Callable[[IConfigurationBuilder], None]
    ) -> "ApplicationBuilder":
        """Configure the configuration builder."""
        self._config_builder = ConfigurationBuilder()
        config_action(self._config_builder)
        self._configuration = self._config_builder.build()

        # Replace any existing configuration registration with the new one
        self.services.add_instance(IConfiguration, self._configuration)
        return self

    def use_configuration(self, configuration: IConfiguration) -> "ApplicationBuilder":
        """Use a pre-built configuration."""
        self._configuration = configuration
        # Replace any existing configuration registration with the new one
        self.services.add_instance(IConfiguration, configuration)
        return self

    @property
    def configuration(self) -> Optional[IConfiguration]:
        """Get the current configuration."""
        return self._configuration

    def configure_services(
        self, callback: Callable[["ApplicationBuilder"], None]
    ) -> "ApplicationBuilder":
        """Mimics builder.ConfigureServices()"""
        callback(self)
        return self

    def use_middleware(
        self, middleware_factory: Callable[..., Any]
    ) -> "ApplicationBuilder":
        """Mimics app.UseMiddleware<T>()"""
        self._middleware.append(middleware_factory)
        return self

    def get_middleware_pipeline(self) -> Any:
        """Get the configured middleware pipeline."""
        try:
            from middleware.middleware_pipeline import (  # type: ignore[import-not-found]
                MiddlewarePipeline,
            )

            pipeline = MiddlewarePipeline()
            for middleware_factory in self._middleware:
                # Pass the factory directly - it should be callable and return middleware instances
                pipeline.use(middleware_factory)
            return pipeline
        except ImportError:
            # Middleware pipeline is optional
            return None

    def build(self) -> ServiceProvider:
        """Mimics builder.Build()"""
        return ServiceProvider(self.services)
