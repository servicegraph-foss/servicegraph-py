from typing import Any, Callable, Dict, Type, TypeVar

# Generic type variable for service types
T = TypeVar("T")

# Common type hints that might be used across the application
ServiceType = TypeVar("ServiceType")
ImplementationType = Type[ServiceType]
ServiceDict = Dict[str, Any]
MiddlewareType = Callable[..., Any]
