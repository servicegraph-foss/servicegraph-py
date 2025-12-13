# Changelog

All notable changes to the servicegraph project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2025-12-13

### Changed
- **Python Compatibility** - Updated minimum required Python version from 3.8 to 3.9 due to syntax compatibility issues

### Fixed
- Resolved syntax compatibility issues that prevented proper operation on Python 3.8

### Breaking Changes
- **Minimum Python Version** - Python 3.9+ is now required. Python 3.8 is no longer supported.

## [0.1.0] - 2025-01-XX **[DEPRECATED]**

> **⚠️ DEPRECATED:** This version is deprecated and will not work correctly due to Python syntax compatibility issues. Please upgrade to version 0.1.1 or later, which requires Python 3.9+.

### Added

#### Core Dependency Injection Features
- **ApplicationBuilder** - Fluent API for configuring dependency injection container
- **ServiceProvider** - Main service resolution engine with recursive dependency discovery
- **Service Lifetimes** - Support for Singleton, Transient, and Scoped service lifetimes
- **Service Registration** - Multiple registration patterns including concrete types, interfaces, factories, and instances
- **Named Services** - Support for multiple implementations of the same interface using named registration
- **Session Management** - Session-scoped transient services with automatic cleanup for stateless environments

#### Configuration Management
- **Configuration System** - Hierarchical configuration with multiple sources
- **JSON File Support** - Load configuration from JSON files with optional file handling
- **Environment Variables** - Automatic environment variable binding with prefix support
- **In-Memory Configuration** - Programmatic configuration for testing and setup
- **Configuration Sections** - Nested configuration access with strongly-typed binding
- **Configuration Hierarchy** - Last-wins precedence for configuration sources

#### Azure Functions Integration
- **Stateless Optimization** - Designed specifically for Azure Functions v2 isolated worker model
- **Cold Start Performance** - Optimized initialization for serverless environments
- **Middleware Pipeline** - Extensible middleware system for cross-cutting concerns
- **Request Context** - Per-request service scoping compatible with Azure Functions execution model

#### Advanced Features
- **Type Safety** - Full type hint support with runtime type checking
- **Circular Dependency Detection** - Automatic detection and prevention of circular service dependencies
- **Memory Management** - Intelligent cleanup with session expiration and weak reference handling
- **Thread Safety** - Concurrent access support for multi-threaded applications
- **Error Handling** - Comprehensive error messages and graceful failure handling

#### Development Experience
- **IntelliSense Support** - Complete type annotations for excellent IDE integration
- **Debugging Tools** - Clear error messages with service resolution context
- **Performance Monitoring** - Built-in performance characteristics for optimization
- **Comprehensive Documentation** - Detailed README with examples and best practices

### Technical Specifications
- **Python Compatibility** - ~~Python 3.8+ support~~ **DEPRECATED - Does not work, use version 0.1.1+ with Python 3.9+**
- **Zero Dependencies** - No external runtime dependencies (except typing-extensions for Python < 3.10)
- **Memory Efficient** - Minimal metadata overhead with automatic cleanup
- **Fast Resolution** - O(1) singleton resolution after initialization, O(n) transient resolution based on dependency depth

### License
- **Apache 2.0 with Commons Clause** - Open source with commercial use restrictions
- **AI Protection** - Special provisions preventing unauthorized AI-based code generation
- **No Relicensing** - Protection against weakening license terms

### Development Tools
- **pytest** - Comprehensive test suite with >95% coverage target
- **mypy** - Static type checking for enhanced code quality
- **black** - Automatic code formatting
- **isort** - Import sorting and organization
- **pre-commit** - Git hooks for code quality enforcement

## [Unreleased]

### Planned Features
- **FastAPI Integration** - Native support for FastAPI dependency injection
- **Async Service Support** - Asynchronous service resolution and lifetime management
- **Service Decorators** - Aspect-oriented programming capabilities
- **Performance Metrics** - Built-in performance monitoring and reporting
- **Advanced Middleware** - Enhanced middleware system with request/response transformation
- **Container Hierarchies** - Parent/child container relationships
- **Convention-based Registration** - Automatic service discovery and registration

---

## Release Notes

### Version 0.1.1 - Python Compatibility Update

This release addresses critical syntax compatibility issues discovered in version 0.1.0. Due to incompatibilities with Python 3.8, the minimum required Python version has been updated to 3.9.

**Key Changes:**
- **Updated Python Requirement** - Minimum Python version is now 3.9+ (previously 3.8+)
- **Syntax Fixes** - Resolved compatibility issues that prevented proper operation on Python 3.8

**Breaking Changes:** 
- Python 3.8 is no longer supported. Users must upgrade to Python 3.9 or later.

**Migration Guide:** 
- Upgrade your Python environment to version 3.9 or later before installing version 0.1.1
- No code changes required; existing code using servicegraph will work without modification

**Deprecation Notice:**
- Version 0.1.0 is now deprecated and should not be used. It contains syntax compatibility issues that prevent proper operation.

### Version 0.1.0 - Initial Release **[DEPRECATED]**

> **⚠️ WARNING:** This version is deprecated due to Python syntax compatibility issues. Use version 0.1.1 or later instead.

This initial release establishes servicegraph as a professional-grade dependency injection framework for Python, with particular strength in stateless runtime environments like Azure Functions. The framework provides enterprise-level DI capabilities while maintaining Python's characteristic simplicity and ease of use.

**Key Highlights:**
- **Production Ready** - Comprehensive error handling and thread safety
- **Azure Functions Optimized** - Designed for serverless and stateless environments
- **Developer Friendly** - Excellent type safety and debugging experience
- **Memory Conscious** - Intelligent cleanup prevents memory leaks in long-running processes
- **Flexible Configuration** - Hierarchical configuration system with multiple sources

**Breaking Changes:** None (initial release)

**Migration Guide:** None required (initial release)

**Known Issues:** 
- **CRITICAL:** Python 3.8 syntax compatibility issues render this version non-functional (fixed in 0.1.1)
- Middleware system is Azure Functions specific; FastAPI integration planned for future release
- Async service resolution not yet supported; planned for future release

**Contributors:**
- Kenneth McManis - Initial implementation and design

**Special Thanks:**
- Python community for inspiration from existing DI frameworks
- Azure Functions team for runtime environment insights

---

*For detailed documentation, examples, and API reference, see [README.md](README.md)*
