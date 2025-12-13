"""
Utilities for dependency injection with named services using Annotated types.
"""

import inspect
from typing import Annotated, Dict, Type, get_args, get_origin


class NamedService:
    """Annotation marker for named service injection."""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"NamedService(name='{self.name}')"


def Named(name: str) -> NamedService:
    """
    Factory function to create named service annotations.

    Usage:
    def __init__(self, parser: Annotated[IDocumentParser, Named("primary")]):
        self.parser = parser
    """
    return NamedService(name)


def extract_named_dependencies(implementation: Type) -> Dict[str, str]:
    """
    Extract named service dependencies from constructor annotations.

    Returns a mapping of parameter_name -> service_name for parameters
    that are annotated with Named().
    """
    named_deps = {}

    try:
        sig = inspect.signature(implementation.__init__)
    except (ValueError, TypeError):
        return named_deps

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        annotation = param.annotation
        if annotation == inspect.Parameter.empty:
            continue

        # Check if this is an Annotated type
        if get_origin(annotation) is Annotated:
            args = get_args(annotation)
            if len(args) >= 2:
                # First arg is the actual type, remaining are metadata
                for metadata in args[1:]:
                    if isinstance(metadata, NamedService):
                        named_deps[param_name] = metadata.name
                        break

    return named_deps


def get_base_type(annotation) -> Type:
    """
    Extract the base type from an Annotated type.

    For Annotated[IDocumentParser, Named("primary")], returns IDocumentParser.
    For regular types, returns the type as-is.
    """
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if args:
            return args[0]  # First argument is the base type

    return annotation
