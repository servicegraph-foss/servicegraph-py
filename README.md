# servicegraph - Lightweight Dependency Injection for Python

A professional-grade dependency injection framework designed for modern Python applications, with first-class support for Azure Functions and extensible middleware capabilities.

## Why servicegraph?

Dependency injection transforms tightly-coupled code into maintainable, testable architectures. While Python's dynamic nature makes DI less critical than in statically-typed languages, complex applications—especially those integrating multiple services, configurations, and external APIs—benefit significantly from structured dependency management.

**servicegraph** provides this structure without the overhead. Designed to excel in both stateless serverless environments and traditional long-running applications, it offers the power of enterprise DI patterns with Python's characteristic simplicity. Its robust resource management and thread safety make it suitable for any Python application architecture.

## Installation

```bash
pip install servicegraph
```

## Quick Start

```python
from servicegraph import ApplicationBuilder, ServiceLifetime
from abc import ABC, abstractmethod

# Define your service interfaces using ABC
class INotificationService(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        """Send a notification message."""
        pass

# Implement the interface
class NotificationService(INotificationService):
    def send(self, message: str) -> None:
        print(f"Sending: {message}")

# Configure and build your application
builder = ApplicationBuilder()
builder.services.add_singleton(INotificationService, NotificationService)

# Get your configured service provider
provider = builder.build()

# Resolve and use services
notification_service = provider.get_service(INotificationService)
notification_service.send("Hello, World!")
```

## Comparison with Other Frameworks

| Feature | servicegraph | dependency-injector | injector | FastAPI Depends |
|---------|------|---------------------|----------|------------------|
| **Learning Curve** | Low (if from .NET) | High | Medium | Low (if using FastAPI) |
| **External Dependencies** | 0 | 6+ | 0 | Many (FastAPI ecosystem) |
| **Async Support** | ✅ Full | ✅ Full | ❌ Limited | ✅ Full |
| **Type Hints Required** | ✅ Yes | ⚠️ Optional | ✅ Yes | ✅ Yes |
| **Scope Management** | ✅ Automatic | ⚠️ Manual | ⚠️ Manual | ✅ Per-request |
| **Lifecycle Hooks** | ✅ Yes | ✅ Yes | ❌ No | ⚠️ Limited |
| **Thread Safety** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Configuration Files** | ❌ Code-only | ✅ YAML/JSON | ❌ Code-only | ❌ Code-only |
| **Serverless Ready** | ✅ Optimized | ⚠️ Requires setup | ⚠️ Requires setup | ⚠️ Limited |
| **Cold Start Impact** | Minimal | Moderate | Minimal | High |
| **.NET-like API** | ✅ Yes | ❌ No | ❌ No | ❌ No |

## When to Use servicegraph

### ✅ Great Fit
- **Migrating from .NET to Python** - familiar patterns reduce friction
- **Serverless/stateless platforms** (Azure Functions, AWS Lambda, etc.) - built-in scope management per invocation
- **Microservices** - zero dependencies means smaller containers
- **Teams with .NET background** - onboarding is instant
- **Projects valuing explicitness** - no magic, clear registration
- **Type-safe codebases** - leverages Python's type system

### ⚠️ Consider Alternatives
- **Need YAML/JSON configuration** → use `dependency-injector`
- **Already using FastAPI** → stick with `Depends()`
- **Want implicit autowiring** → consider `pinject` (if risk of abandonment is acceptable)
- **Complex multi-tenant scenarios** → `dependency-injector` has more enterprise features

### ❌ Not Ideal For
- **Python 2.7 or <3.8** - requires modern type hints
- **Projects avoiding type hints** - core to servicegraph's design
- **Need for decorators on every class** - servicegraph is registration-based, not decorator-based

## Core Concepts

### Service Discovery and Resolution

servicegraph uses a recursive resolution mechanism that automatically discovers and instantiates dependencies. When you request a service, the container:

1. **Locates the registration** - Finds the concrete type mapped to your interface
2. **Analyzes dependencies** - Inspects the constructor for required parameters
3. **Recursively resolves** - Automatically instantiates any dependencies of dependencies
4. **Manages lifecycle** - Applies the appropriate lifetime scope (singleton, transient, scoped)
5. **Returns the instance** - Provides a fully-configured object ready for use

This eliminates the manual wiring typically required in Python applications while maintaining full control over object creation.

> **Note on Constructor Analysis**: servicegraph gracefully handles classes without explicit constructors (those that inherit Python's default `object.__init__`). The container automatically detects when a class has no custom constructor and creates simple factory functions that instantiate the class directly, without attempting dependency injection. This means you can register and resolve both complex services with dependencies and simple data classes or utility classes seamlessly.

### Interface Design Requirements

**servicegraph enforces proper interface design using Python's Abstract Base Classes (ABC):**

```python
from abc import ABC, abstractmethod

# ✅ CORRECT: Use ABC with @abstractmethod decorators
class IPaymentProcessor(ABC):
    @abstractmethod
    def process_payment(self, amount: float, method: str) -> bool:
        """Process a payment transaction."""
        pass
    
    @abstractmethod
    def validate_payment_method(self, method: str) -> bool:
        """Validate payment method."""
        pass

# ✅ CORRECT: Concrete implementations must inherit the interface
class StripePaymentProcessor(IPaymentProcessor):
    def process_payment(self, amount: float, method: str) -> bool:
        # Implementation here
        return True
    
    def validate_payment_method(self, method: str) -> bool:
        # Implementation here
        return method in ["card", "bank_transfer"]

# ❌ INCORRECT: Plain classes without ABC inheritance
class IPaymentProcessor:  # Missing ABC inheritance
    def process_payment(self, amount: float, method: str) -> bool:
        pass  # Missing @abstractmethod decorator
```

**Why this matters:**
- **Type Safety**: Ensures interfaces are properly defined contracts
- **IDE Support**: Excellent IntelliSense and error detection
- **Runtime Validation**: Prevents instantiation of incomplete implementations
- **Documentation**: Abstract methods serve as living documentation

### Configuration Integration

servicegraph includes a robust configuration system that seamlessly integrates with dependency injection:

```python
from servicegraph import ApplicationBuilder, IConfiguration
from abc import ABC, abstractmethod

def configure_app():
    builder = ApplicationBuilder()
    
    # Basic configuration setup
    def setup_config(config):
        config.add_json_file("appsettings.json", optional=True)
        config.add_environment_variables("")
        return config
    
    builder.configure_configuration(setup_config)
    
    # Configuration is automatically available for injection
    provider = builder.build()
    config = provider.get_service(IConfiguration)
    
    api_url = config.get_value("API_BASE_URL")
```

**Key Features:**

- **Type Preservation**: Configuration values retain their original types (int, bool, float, str, dict, list) from JSON files or environment variables
- **Case-Insensitive Lookups**: Keys are matched case-insensitively (`database:port`, `DATABASE:PORT`, and `Database:Port` all work)
- **Hierarchical Merging**: Multiple configuration sources merge intelligently, with later sources overriding earlier ones regardless of key casing
- **Convention Over Configuration**: Provides sensible defaults while remaining highly customizable

```python
# Type preservation examples
config.get_value("api:timeout")      # Returns: 30 (int from JSON)
config.get_value("feature:enabled")  # Returns: True (bool from JSON)
config.get_value("database:port")    # Returns: "5432" (str from env var)
config.get_value("cache:ttl")        # Returns: 3.5 (float from JSON)

# Case-insensitive lookups - all equivalent
config.get_value("database:connection_string")
config.get_value("DATABASE:CONNECTION_STRING")
config.get_value("Database:ConnectionString")
```

The configuration system provides sensible defaults while remaining highly customizable, following the principle of convention over configuration.

## Service Lifetimes

Understanding service lifetimes is crucial for both performance and correctness in dependency injection.

### Singleton
```python
builder.services.add_singleton(INotificationService, NotificationService)
```
**What happens**: One instance created for the entire application lifetime.
**Use when**: Services are stateless, expensive to create, or need to maintain state across requests.
**Memory impact**: Minimal - single instance regardless of usage frequency.

### Transient
```python
builder.services.add_transient(INotificationService, NotificationService)

# Basic usage - new instance every time
notification_service = provider.get_service(INotificationService)

# Session-scoped transients - same instance within a session
session_id = "session_abc123"
service1 = provider.get_service(INotificationService, session_id)
service2 = provider.get_service(INotificationService, session_id)  # Same instance
service3 = provider.get_service(INotificationService, "different_session")  # New instance

# Clean up session when done
provider.dispose_session(session_id)
```
**What happens**: New instance created every time the service is requested, unless a session_id is provided.
**Use when**: Services are lightweight, stateful per operation, or you need isolation between usages.
**Session management**: When you provide a `session_id`:
- **New session**: If the session doesn't exist, a new session is created with a fresh service instance
- **Existing session**: If the session exists, the same service instance is returned
- **Per-service tracking**: Each service type gets its own instance within a session
**Client considerations**: 
- Use `dispose_session(session_id)` to clean up session-scoped instances
- Sessions automatically expire after 30 minutes of inactivity
- Transient services in long-running operations should be explicitly disposed if they implement `IDisposable` or have cleanup requirements.

### Scoped
```python
builder.services.add_scoped(INotificationService, NotificationService)

# Direct resolution - must be used within a 'with' statement
with provider.get_service(INotificationService) as notification_service:
    notification_service.send("Scoped message")
# Service is automatically disposed when exiting the 'with' block

# With optional session_id (needed when scoped service depends on transients)
with provider.get_service(IDatabaseConnection, session_id="request_123") as db:
    # Transient dependencies of this scoped service will share this session
    db.execute_query()
# Service disposed, but session persists for other services to reuse transients

# Dependency injection - graceful behavior without context manager
class EmailService:
    def __init__(self, notification_service: INotificationService):
        self.notification_service = notification_service  # ✅ Works seamlessly

builder.services.add_transient(EmailService)
email_service = provider.get_service(EmailService)  # ✅ No context manager needed
```
**What happens**: One instance per scope, automatically disposed when the scope ends.
**Use when**: You need per-request state with guaranteed cleanup (database connections, file handles, etc.).
**Session ID**: Optional parameter that creates a session for consistent transient resolution within the scoped service's dependencies.

**Graceful Dependency Injection**: servicegraph intelligently handles scoped services differently based on context:
- **Direct resolution** (`provider.get_service(IScopedService)`): Returns a context manager wrapper that enforces the `with` pattern
- **Dependency injection** (constructor parameter): Automatically unwraps to the raw instance—no context manager required
- **Automatic session management**: When used as dependencies, scoped services automatically inherit the session context from their parent scope
- **Cascading cleanup**: All scoped dependencies are tracked and disposed together when the parent scope ends

**Why this matters**: You can safely inject scoped services (like database connections) into transient or singleton services without worrying about context manager syntax. The framework ensures proper lifecycle management and resource cleanup automatically.

**Session persistence with transients** (when using `session_id`): When a scoped service depends on a transient service and you provide a `session_id`, the transient instance persists in the session beyond the scoped service's lifecycle:
```python
builder.services.add_scoped(IDatabaseConnection, DatabaseConnection)
builder.services.add_transient(IQueryBuilder, QueryBuilder)  # Used by DatabaseConnection

# WITH session_id: Transients are reused within the session
with provider.get_service(IDatabaseConnection, session_id="request_123") as db1:
    # QueryBuilder instance #1 created and cached in session
    db1.execute_query()  # Uses QueryBuilder #1

# First scoped service disposed, but QueryBuilder #1 still in session

with provider.get_service(IDatabaseConnection, session_id="request_123") as db2:
    # QueryBuilder instance #1 reused from session
    db2.execute_query()  # Uses same QueryBuilder #1

# Session cleanup - explicitly dispose when request is complete
provider.dispose_session("request_123")  # Now QueryBuilder #1 is cleaned up

# WITHOUT session_id: Each scoped service gets fresh transient instances
with provider.get_service(IDatabaseConnection) as db:
    # QueryBuilder created, used, and may be garbage collected after disposal
    db.execute_query()
```

**Key Point**: The `session_id` parameter is **optional**. Use it only when you need consistent transient instances across multiple scoped service resolutions within the same logical operation (like a web request or function invocation).

**Behind the scenes**: servicegraph wraps scoped services in a `ScopedServiceContextManager` that enforces proper usage for direct resolution while gracefully unwrapping for dependency injection.
**Disposal behavior**: The context manager automatically calls `dispose()` or `close()` methods if your service implements them, but scoped services don't need to implement these methods—the `with` pattern works with any service. All scoped dependencies created during a scope are tracked and disposed together.

### Lifecycle Dependency Rules

**servicegraph enforces strict lifetime compatibility rules** to prevent subtle bugs where longer-lived services depend on shorter-lived ones. These validations occur at registration time, catching configuration errors early.

**The Sliding Scale Rule**:
```
Singleton (longest lifetime)
    ↓ can depend on
Transient (medium lifetime)
    ↓ can depend on
Scoped (shortest lifetime)
```

Services can only depend on services with equal or longer lifetimes. Dependencies "up" the scale are allowed; dependencies "down" the scale are prohibited.

**Validation Rules**:

1. **Singleton services CANNOT depend on Transient or Scoped services**
   ```python
   # ❌ INVALID - Singleton depending on Transient
   class SingletonService:
       def __init__(self, transient: TransientService):  # ERROR at registration!
           self.transient = transient
   
   builder.services.add_transient(TransientService)
   builder.services.add_singleton(SingletonService)  
   # ValueError: Singleton services cannot depend on transient services
   ```
   
   **Why prohibited**: Singletons are created once and reused. If a singleton depends on a transient, it would capture a single transient instance, violating the transient's "new instance every time" contract.

2. **Transient services CANNOT depend on Scoped services**
   ```python
   # ❌ INVALID - Transient depending on Scoped
   class TransientService:
       def __init__(self, scoped: ScopedService):  # ERROR at registration!
           self.scoped = scoped
   
   builder.services.add_scoped(ScopedService)
   builder.services.add_transient(TransientService)
   # ValueError: Transient services cannot depend on scoped services
   ```
   
   **Why prohibited**: Transient services can be created outside of a scope context, but scoped services require scope context. This would create orphaned scoped instances.

3. **Valid Dependency Patterns** ✅
   ```python
   # ✅ VALID - Scoped can depend on Transient
   class ScopedService:
       def __init__(self, transient: TransientService):
           self.transient = transient
   
   # ✅ VALID - Scoped can depend on Singleton
   class ScopedService:
       def __init__(self, singleton: SingletonService):
           self.singleton = singleton
   
   # ✅ VALID - Transient can depend on Singleton
   class TransientService:
       def __init__(self, singleton: SingletonService):
           self.singleton = singleton
   
   # ✅ VALID - Scoped can depend on Scoped
   class ScopedService:
       def __init__(self, other_scoped: OtherScopedService):
           self.other_scoped = other_scoped
   ```

**Error Messages**:
When you violate these rules, servicegraph provides clear, actionable error messages:
```
ValueError: Invalid dependency in SingletonService: Singleton services cannot depend on 
transient services.
Parameter 'transient' of type 'TransientService' is registered as transient, but 
SingletonService is a singleton.
This would break singleton semantics as the dependency could have different instances.
Solution: Register 'TransientService' as a singleton, or change SingletonService to 
transient/scoped.
```

**Design Philosophy**: These restrictions enforce best practices and prevent memory leaks, dangling references, and unpredictable behavior. While they may seem restrictive, they guide you toward more maintainable architectures. If you find yourself needing to violate these rules, consider whether your service lifetimes are correctly chosen for their responsibilities.

## Advanced Registration Patterns

### Primitive Type Parameters in Constructors

**Understanding the Limitation**

Dependency injection systems are designed to inject **complex types** (classes, interfaces) but cannot automatically inject **primitive types** (str, int, float, bool, list, dict, set, tuple, bytes). This is a fundamental limitation across all DI frameworks because there's no way for the container to know what value a primitive parameter should have without explicit configuration.

**What Happens:**

```python
class EmailService:
    def __init__(self, smtp_host: str, smtp_port: int, use_ssl: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_ssl = use_ssl

# ⚠️ IMPROPER: Direct registration without factory
builder.services.add_singleton(IEmailService, EmailService)

# What happens:
# 1. Warning is logged: "Parameter 'smtp_host' of type 'str' in EmailService 
#    constructor is a primitive type with no default value..."
# 2. Service is created successfully with None for smtp_host and smtp_port
# 3. Service with None values is returned - no crash during creation
# 4. Error occurs LATER when you try to use the None values:

service = provider.get_service(IEmailService)
print(service.smtp_host)  # None - service exists but has None
service.smtp_host.lower() # ❌ AttributeError: 'NoneType' object has no attribute 'lower'
```

**The Design Decision:**

servicegraph follows the principle that **the DI container should not crash your application**. Instead:
- The service is created successfully (with `None` for primitive parameters without defaults)
- Warnings are logged to alert you of the configuration issue
- The error occurs when **you** try to use the improperly configured service
- This makes the problem obvious during development while keeping the framework resilient

**This is developer responsibility**, not a framework bug. If your service has primitives without defaults, you must use one of the proper registration patterns below.

**✅ Proper Solutions:**

**1. Factory Registration (Recommended for Configuration-Based Values)**

Use a factory function to provide primitive values explicitly:

```python
def email_service_factory(provider: ServiceProvider) -> EmailService:
    # Option A: Hardcoded values
    return EmailService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        use_ssl=True
    )
    
    # Option B: From configuration
    config = provider.get_service(IConfiguration)
    return EmailService(
        smtp_host=config.get_value("email:smtp_host"),
        smtp_port=int(config.get_value("email:smtp_port")),
        use_ssl=config.get_value("email:use_ssl", True)
    )

builder.services.add_factory(IEmailService, email_service_factory)
```

**2. Default Values in Constructor (Simplest for Constants)**

Provide sensible defaults in your service constructor:

```python
class EmailService:
    def __init__(
        self, 
        smtp_host: str = "smtp.example.com",  # ✅ Has default
        smtp_port: int = 587,                 # ✅ Has default
        use_ssl: bool = True                  # ✅ Has default
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_ssl = use_ssl

# Now direct registration works fine
builder.services.add_singleton(IEmailService, EmailService)
```

**3. Instance Registration (For Pre-Configured Objects)**

Create and configure the instance before registration:

```python
email_service = EmailService(
    smtp_host="smtp.example.com",
    smtp_port=587,
    use_ssl=True
)

builder.services.add_instance(IEmailService, email_service)
```

**4. Mixed Approach (Primitives with Defaults + Complex Type Injection)**

This is the recommended pattern for most services:

```python
class NotificationService:
    def __init__(
        self, 
        email_service: IEmailService,        # ✅ Complex type - will be injected
        app_name: str = "MyApp",             # ✅ Primitive with default
        max_retries: int = 3                 # ✅ Primitive with default
    ):
        self.email_service = email_service   # Automatically injected
        self.app_name = app_name            # Uses default unless overridden by factory
        self.max_retries = max_retries

# Direct registration works - complex type injected, primitives use defaults
builder.services.add_singleton(NotificationService)

# Or use factory to override defaults
builder.services.add_factory(
    NotificationService,
    lambda p: NotificationService(
        email_service=p.get_service(IEmailService),  # Injected
        app_name="CustomApp",                        # Override default
        max_retries=5                                # Override default
    )
)
```

**Key Takeaways:**

- **Primitive types cannot be auto-injected** - this is by design in all DI systems
- **The application won't crash during service creation** - you'll get warnings and `None` values
- **Errors occur when you try to use `None`** - making the issue obvious during development
- **Use factories, defaults, or instances** - these are the proper patterns for primitives
- **Complex types are still auto-injected** - only primitives require special handling

This behavior encourages proper service design where configuration values (primitives) are separated from dependencies (complex types), leading to more maintainable and testable code.

### Factory Registration

For complex object creation scenarios, factories provide ultimate flexibility:

```python
def create_api_client_factory(provider: ServiceProvider) -> Callable[[], ApiClient]:
    config = provider.get_service(IConfiguration)
    endpoint = config.get_value("API_ENDPOINT")
    
    def create_client() -> ApiClient:
        return ApiClient(
            endpoint=endpoint,
            api_key=config.get_value("API_KEY")
        )
    
    return create_client

builder.services.add_factory(
    Callable[[], ApiClient],
    create_api_client_factory
)
```

**Class composition benefit**: Factory registration excels when object creation involves multiple steps, conditional logic, or external resource initialization. The factory pattern also enables lazy loading—expensive resources are only created when actually needed.

### Named Service Registration

When you need multiple implementations of the same interface:

```python
# Register multiple notification providers
builder.services.add_named_singleton("smtp", INotificationService, SmtpNotificationService)
builder.services.add_named_singleton("push", INotificationService, PushNotificationService)

# Resolve specific implementations
smtp_service = provider.get_named_service("smtp", INotificationService)
push_service = provider.get_named_service("push", INotificationService)
```

**Why it matters**: Named registration is essential for scenarios like multi-tenant applications, A/B testing implementations, or fallback service patterns. Rather than creating separate interfaces for functionally identical services, named registration maintains clean abstractions while providing implementation flexibility.

## Design Philosophy

servicegraph was born from a specific need: **bringing .NET's familiar DI patterns to Python with first-class support for modern deployment architectures**.

### Core Principles

1. **Zero Surprises for .NET Developers**
   ```csharp
   // C# ASP.NET Core
   services.AddTransient<IMyService, MyService>();
   ```
   ```python
   # Python servicegraph
   services.add(MyService, IMyService, lifetime=ServiceLifetime.TRANSIENT)
   ```

2. **No Hidden Dependencies**
   - Every import is from `servicegraph` or Python stdlib
   - No surprise package installations
   - Predictable deployment sizes

3. **Explicit Resource Management**
   - Scopes are visible: `with provider.get_service(IScopedService, session_id) as service:`
   - Lifecycle hooks are obvious: `Disposable` protocol
   - No magic cleanup - you control when

4. **Type Safety First**
   - Type hints aren't optional - they're the API
   - Runtime type checking catches errors early
   - IDE autocomplete works perfectly

5. **Stateless Architecture Optimized**
   - Scope-per-invocation pattern built-in
   - Thread-safe for concurrent executions
   - Minimal cold start overhead for serverless platforms

## Real-World Use Case: Serverless Platforms

**Problem**: Serverless platforms (Azure Functions, AWS Lambda, etc.) can have concurrent executions in the same process. Traditional singleton patterns can cause data bleed between invocations.

**servicegraph Solution**:
```python
from servicegraph import ApplicationBuilder, ServiceLifetime
import azure.functions as func  # or AWS Lambda handler, etc.

# Create application once at startup
builder = ApplicationBuilder()
builder.services.add_scoped(IRequestContext, RequestContext)  # Per-invocation
builder.services.add_singleton(IDatabaseClient, DatabaseClient)  # Shared connection
builder.services.add_transient(IMyService, MyService)
provider = builder.build()

def main(req: func.HttpRequest) -> func.HttpResponse:
    # Use unique session per invocation - no data bleed!
    session_id = req.invocation_id  # or generate unique ID
    
    # Scoped service automatically manages lifecycle
    with provider.get_service(IRequestContext, session_id=session_id) as context:
        context.user_id = req.params.get('user_id')
        
        # Other services in same session share scoped dependencies
        service = provider.get_service(IMyService, session_id=session_id)
        result = service.process()
        
    # Scoped services auto-disposed, session cleaned up
    provider.dispose_session(session_id)
    return func.HttpResponse(result)
```

**Why not dependency-injector?** 
- Requires manual scope creation boilerplate
- External dependencies increase cold start time
- Configuration overhead for simple scenarios

**Why not injector?**
- No built-in scope management
- Manual lifetime tracking required
- Less intuitive for .NET developers

**Why not FastAPI Depends?**
- Not designed for serverless platforms
- Requires FastAPI framework overhead

## Common Patterns

### Application Startup Pattern

The recommended pattern follows .NET's familiar startup conventions: centralize configuration in a setup module, then initialize once at application startup.

**1. Create a Setup Module** (`program.py` or `app_setup.py`):

```python
from typing import Callable
from servicegraph import ApplicationBuilder, ServiceProvider, IConfiguration
from interfaces.i_email_service import IEmailService
from interfaces.i_database import IDatabaseConnection
from interfaces.i_api_client import IApiClient
from services.email_service import EmailService
from services.database import DatabaseConnection
from services.api_client import ApiClient

def create_api_client_factory(provider: ServiceProvider) -> Callable[[], IApiClient]:
    """Factory function that captures config and returns a client creator."""
    config = provider.get_service(IConfiguration)
    base_url = config.get_value("API_BASE_URL")
    api_key = config.get_value("API_KEY")
    timeout = config.get_value("API_TIMEOUT", 30)
    
    def create_client() -> IApiClient:
        return ApiClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout
        )
    
    return create_client

def configure_services(builder: ApplicationBuilder):
    """Register all application services."""
    # Register complex service factories
    builder.services.add_factory(
        Callable[[], IApiClient],
        create_api_client_factory
    )
    
    # Register business logic services
    builder.services.add_singleton(IEmailService, EmailService)
    builder.services.add_transient(IDataProcessor, DataProcessor)
    builder.services.add_scoped(IDatabaseConnection, DatabaseConnection)

def configure_middleware(builder: ApplicationBuilder, environment: str = "Development"):
    """Configure middleware pipeline (optional - framework-specific)."""
    import os
    
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Add middleware components (if applicable to your platform)
    add_logging_middleware(builder, log_level)
    add_authentication_middleware(builder)

def create_app(environment: str = "Development") -> ServiceProvider:
    """
    Create the application with fully configured services.
    Call this once at application startup.
    
    Returns:
        Configured ServiceProvider
    """
    builder = ApplicationBuilder()
    
    # Configure configuration sources (hierarchical override pattern)
    def configure_config(config):
        return (config
                .add_json_file("config/appsettings.json", optional=True)
                .add_json_file(f"config/appsettings.{environment.lower()}.json", optional=True)
                .add_environment_variables(""))  # Load all environment variables
    
    builder.configure_configuration(configure_config)
    
    # Register services
    configure_services(builder)
    
    # Configure middleware (optional)
    if supports_middleware():
        configure_middleware(builder, environment)
    
    # Build and return
    return builder.build()
```

**2. Initialize Once at Application Startup**:

```python
# Serverless function example (Azure Functions, AWS Lambda, etc.)
from program import create_app

# Create once - reused across all function invocations
service_provider = create_app("Production")

def handler(event, context):
    # Resolve services as needed
    processor = service_provider.get_service(IDataProcessor)
    result = processor.process(event.get('data'))
    return {"statusCode": 200, "body": result}
```

```python
# Web application example (Flask/FastAPI)
from program import create_app

# Initialize at module level
app_provider = create_app()

@app.route('/api/process')
def process_data():
    processor = app_provider.get_service(IDataProcessor)
    result = processor.process(request.json)
    return jsonify(result)
```

```python
# Background worker/script example
from program import create_app

def main():
    provider = create_app()
    
    # Resolve top-level service
    worker = provider.get_service(IBackgroundWorker)
    worker.run()

if __name__ == "__main__":
    main()
```

### Service Resolution Patterns

**Direct Resolution** (Top-level services):
```python
# Resolve when you need it
service = provider.get_service(IMyService)
result = service.do_work()
```

**Constructor Injection** (Preferred - automatic dependency resolution):
```python
class DocumentProcessor:
    def __init__(
        self,
        parser: IDocumentParser,           # Automatically injected
        email: IEmailService,              # Automatically injected
        config: IConfiguration             # Automatically injected
    ):
        self.parser = parser
        self.email = email
        self.config = config
    
    def process(self, document: bytes):
        parsed = self.parser.parse(document)
        self.email.send(f"Processed: {parsed}")

# Register and resolve - dependencies are automatically injected
builder.services.add_transient(DocumentProcessor)
processor = provider.get_service(DocumentProcessor)  # All dependencies resolved!
```

**Scoped Services** (Request/operation lifetime):
```python
def handle_request(request_id: str):
    # Simple usage - no session_id needed if scoped service has no transient dependencies
    with provider.get_service(IDatabaseConnection) as db:
        db.execute_query()
    
    # With session_id - use when scoped service depends on transients
    # This ensures transient dependencies are reused within the same request
    with provider.get_service(IDatabaseConnection, session_id=request_id) as db:
        # Resolve other services within this scope
        processor = provider.get_service(IRequestProcessor, session_id=request_id)
        
        # Use services - all scoped dependencies share this session
        processor.process(db)
        
    # Scoped service and its dependencies automatically disposed here
    # Clean up session when request is complete
    provider.dispose_session(request_id)
```

**When to use `session_id` with scoped services**:
- ✅ **Use `session_id`** when your scoped service depends on transient services that should be reused within the same request/operation
- ✅ **Use `session_id`** when you have multiple scoped services in the same request that should share transient dependencies
- ❌ **Skip `session_id`** for simple scoped services with no transient dependencies (database connections, file handles, etc.)

### Factory Pattern for Complex Configuration

**When to use**: Services that need runtime configuration values or complex initialization.

```python
def create_api_client_factory(provider: ServiceProvider) -> IApiClient:
    """Factory resolves dependencies and applies configuration."""
    config = provider.get_service(IConfiguration)
    logger = provider.get_service(ILogger)
    
    # Complex initialization logic
    base_url = config.get_value("api:base_url")
    timeout = config.get_value("api:timeout", 30)
    
    client = ApiClient(
        base_url=base_url,
        timeout=timeout,
        retry_policy=ExponentialBackoff(max_attempts=3)
    )
    
    logger.info(f"Created API client for {base_url}")
    return client

builder.services.add_factory(IApiClient, create_api_client_factory)
```

### Multi-Tenant Pattern (Named Services)

**When to use**: Multiple implementations of the same interface for different contexts.

```python
# Register multiple storage providers
builder.services.add_named_singleton("blob", IStorageProvider, BlobStorageProvider)
builder.services.add_named_singleton("file", IStorageProvider, FileStorageProvider)
builder.services.add_named_singleton("sql", IStorageProvider, SqlStorageProvider)

# Resolve based on runtime context
def store_document(tenant_config: dict, document: bytes):
    storage_type = tenant_config["storage_type"]  # "blob", "file", or "sql"
    storage = provider.get_named_service(storage_type, IStorageProvider)
    storage.save(document)
```

### Testing Pattern

**Override services for testing**:

```python
def create_test_app() -> ServiceProvider:
    """Create app with test doubles."""
    builder = ApplicationBuilder()
    
    # Use mocks/fakes for external dependencies
    builder.services.add_singleton(IEmailService, FakeEmailService)
    builder.services.add_singleton(IStorageProvider, InMemoryStorage)
    
    # Use real implementations for business logic
    builder.services.add_transient(DocumentProcessor)
    
    return builder.build()

def test_document_processing():
    provider = create_test_app()
    processor = provider.get_service(DocumentProcessor)
    
    result = processor.process(test_document)
    
    assert result.status == "success"
```

## Platform Integrations

### Azure Functions

servicegraph provides first-class support for Azure Functions v2 (isolated worker model):

```python
import azure.functions as func
from servicegraph import ApplicationBuilder

def create_app():
    builder = ApplicationBuilder()
    
    # Configure services
    builder.services.add_singleton(INotificationService, NotificationService)
    
    return builder.build()

# Initialize once, use across function invocations
app_provider = create_app()

def main(req: func.HttpRequest) -> func.HttpResponse:
    # Services are available immediately
    notification_service = provider.get_service(INotificationService)
    
    # Your function logic here
    return func.HttpResponse("Success")
```

### Middleware Support

servicegraph includes an extensible middleware pipeline for cross-cutting concerns like logging, authentication, and validation.

**Current Implementation: Azure Functions**

```python
from servicegraph.middleware import MiddlewarePipeline
import azure.functions as func

def configure_middleware(builder: ApplicationBuilder):
    # Add logging, authentication, validation, etc.
    add_logging_middleware(builder, connection_string, environment)
    add_authentication_middleware(builder)

def main(req: func.HttpRequest) -> func.HttpResponse:
    # Middleware automatically processes request/response
    return middleware_pipeline.execute(req, your_handler)
```

**Framework Support Status**:
- ✅ **Azure Functions v2** - Full middleware support for HTTP triggers
- 🔄 **FastAPI** - Planned (contributions welcome)
- 🔄 **Flask/Django** - Planned (contributions welcome)
- 🔄 **AWS Lambda** - Planned (contributions welcome)

The middleware pattern is designed to be framework-agnostic. Current implementation focuses on Azure Functions HTTP triggers, but the architecture supports extension to other frameworks. Contributions for additional framework support are encouraged.

## Configuration Management

### File-Based Configuration

**Basic Setup (Single Source):**
```python
def setup_config(config):
    config.add_json_file("appsettings.json", optional=True)
    return config
```

**Chained Setup (Multiple Sources):**
```python
def setup_config(config):
    return (config
            .add_json_file("appsettings.json", optional=True)
            .add_json_file(f"appsettings.{environment}.json", optional=True)
            .add_environment_variables("APP_"))  # Prefix for environment variables
```

**Environment Variable Naming Convention:**

When using environment variables for nested configuration, use **double underscores (`__`)** to represent hierarchy:

```python
# Environment variables for nested configuration
os.environ["APP_DATABASE__HOST"] = "localhost"
os.environ["APP_DATABASE__PORT"] = "5432"
os.environ["APP_DATABASE__NAME"] = "mydb"

# After removing prefix "APP_", becomes:
# {"DATABASE": {"HOST": "localhost", "PORT": "5432", "NAME": "mydb"}}

# Access using colon notation
config.get_value("database:host")  # Returns "localhost"
config.get_value("database:port")  # Returns "5432"
```

**Key points:**
- Single underscore (`_`) separates words within the same key
- Double underscore (`__`) creates nested configuration levels
- After prefix removal, `__` is converted to `:` for hierarchical access

**When to use each:**
- **Basic setup**: Simple applications with one configuration source, or when you prefer explicit calls
- **Chained setup**: Applications with multiple configuration layers (base + environment + runtime overrides)

### Hierarchical Configuration
Configuration sources are processed in order, with later sources overriding earlier ones. This enables the standard pattern:
1. **Base configuration** (`appsettings.json`)
2. **Environment-specific overrides** (`appsettings.production.json`)
3. **Runtime overrides** (environment variables)

**Case-Insensitive Merging:** The configuration system merges sources intelligently regardless of key casing. For example:
```python
# appsettings.json (lowercase keys)
{
  "database": {
    "host": "localhost",
    "port": 5432
  }
}

# Environment variable (uppercase keys)
os.environ["APP_DATABASE__PORT"] = "3306"

# Result after merging - the PORT override matches "port" case-insensitively
config.get_value("database:port")  # Returns: "3306"
config.get_value("DATABASE:PORT")  # Returns: "3306" (same value, case-insensitive)
```

This ensures environment variables and configuration files work together seamlessly, regardless of naming conventions used in different sources.

### Strongly-Typed Configuration
```python
@dataclass
class ApiConfig:
    base_url: str
    timeout: int
    retry_count: int

# Register configuration objects
builder.services.configure(ApiConfig, "Api")

# Inject typed configuration
def __init__(self, api_config: ApiConfig):
    self.config = api_config
```

## Important Considerations

### Memory Management Philosophy

servicegraph provides **intelligent memory management** designed for both stateless and long-running environments. This design reflects its versatility across different runtime platforms.

**What this means for you**:
- **Singleton services**: Persist for the application lifetime with automatic cleanup on shutdown—suitable for both stateless environments and long-running applications
- **Transient services**: Created and released per request with session-based cleanup to prevent memory leaks
- **Scoped services**: Guaranteed cleanup through context manager pattern
- **Session management**: Automatic expiration (30 minutes) prevents memory accumulation in long-running processes

### Runtime Environment Flexibility

servicegraph was architected for **versatile deployment** across different platforms:

**Stateless platforms** (optimized):
- Azure Functions
- AWS Lambda  
- Container-based microservices
- Serverless environments

**Long-running applications** (fully supported):
- Web applications and APIs
- Background services and workers
- Desktop applications
- Multi-threaded server applications

**Design benefits**:
- **Fast startup**: Minimal overhead during container initialization
- **Predictable lifecycle**: Service lifetimes align with request/response cycles or application lifetime
- **Resource efficiency**: Automatic cleanup prevents memory leaks in both short and long-lived processes
- **Thread safety**: Concurrent access support for multi-threaded applications

### When to Consider Alternatives to servicegraph

Consider alternatives if you're building:
- **Applications requiring complex object lifecycle management** beyond the three standard lifetimes (singleton, transient, scoped)
- **Systems with sophisticated disposal patterns** that need more than basic `dispose()`/`close()` method calling
- **Applications with complex dependency graphs** that require advanced features like conditional registration, decorators, or aspect-oriented programming

### Performance Characteristics

- **Service resolution**: O(1) for singletons after first resolution, O(n) for transients where n is dependency depth
- **Memory footprint**: Minimal metadata overhead with automatic session cleanup; actual memory usage depends on your registered services
- **Startup cost**: Linear with number of singleton services requiring immediate initialization
- **Long-running stability**: Session expiration and automatic cleanup prevent memory accumulation over time

## Honest Trade-offs

### What servicegraph Doesn't Do (By Design)

- **No configuration files** - Registration is code-only. If you need YAML/JSON config, use `dependency-injector`.
- **No automatic discovery** - You must explicitly register services. This is intentional for clarity.
- **No decorators-everywhere** - Unlike `injector`, you don't decorate every class. Registration is centralized.
- **No web framework integration** - servicegraph is framework-agnostic. FastAPI's `Depends()` is better if you're all-in on FastAPI.
- **No validation framework** - servicegraph injects dependencies; it doesn't validate them. Use Pydantic/etc. separately.

### What This Means

If you want a batteries-included, enterprise-grade DI container with every feature imaginable, `dependency-injector` is more mature.

If you want the **simplest possible DI system that feels like .NET**, especially for serverless and stateless architectures, servicegraph is your tool.

> **"Dependency Injection for Python developers who miss .NET, or serverless developers who want sanity."**

## Contributing

We welcome contributions! Whether it's bug reports, feature requests, or code contributions, please feel free to engage with the project.

## License

This project is licensed under the **Apache License 2.0 with Commons Clause** - see the [LICENSE](LICENSE) file for complete details.

### Key License Terms

- **Open Source**: Full access to source code, modification, and distribution rights
- **Commercial Use Restrictions**: The software may not be sold or offered as a paid service
- **AI Protection**: Special provisions prevent unauthorized AI-based code generation or redistribution of substantially similar systems
- **Internal Use**: Unrestricted use within your organization and integration into broader applications

**Important**: While the source code is freely available, commercial resale and AI-based reproduction are specifically restricted. This ensures the framework remains open for legitimate use while protecting against unauthorized commercialization.

## Development Philosophy

### Standard Library First

**servicegraph is committed to minimizing external dependencies** for core functionality. This design principle ensures:

- **Zero dependency conflicts** with your existing projects
- **Lightweight installation** that doesn't bloat your environment
- **Maximum compatibility** across different Python versions and platforms
- **Long-term stability** since standard library APIs rarely change

**What this means for contributors:**
- Core dependency injection functionality must use only Python's standard library
- External dependencies are acceptable only for:
  - Testing frameworks (pytest, etc.)
  - Platform-specific integrations (Azure Functions SDK, etc.)
  - Optional features clearly documented as requiring additional packages

**Code review criteria:**
All contributions will be evaluated against this standard library requirement. Pull requests introducing unnecessary external dependencies for core functionality will be respectfully declined with suggestions for standard library alternatives.

**Current external dependencies:**
- **None** for core DI functionality
- Testing and Azure Functions integration may use appropriate external libraries

This philosophy keeps servicegraph lean, predictable, and suitable for any Python environment without imposing additional complexity on your projects.

---

**Built for the modern Python developer who values clean architecture without sacrificing simplicity.**
