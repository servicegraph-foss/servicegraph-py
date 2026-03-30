# servicegraph Copilot Architecture Reference

## Scope
- Keep the package focused on dependency injection (registration, lifetimes, resolution, and disposal semantics).
- Favor .NET-style developer ergonomics while staying Pythonic.
- Avoid adding features that are not directly DI-related.

## High-Level Runtime Topology

```mermaid
flowchart TD
	U[User Code] --> AB[ApplicationBuilder]

	AB -->|entry| ABM1[configure_services(callback)]
	AB -->|entry| ABM2[configure_configuration(config_action)]
	AB -->|entry| ABM3[use_configuration(configuration)]
	AB -->|entry| ABM4[build()]

	AB --> SC[ServiceCollection]
	AB --> CB[ConfigurationBuilder]
	CB --> CFG[IConfiguration]
	AB --> CFG

	SC -->|registrations + factories + lifetimes| SP[ServiceProvider]
	ABM4 --> SP

	SP -->|accessor| SPM1[get_service(type, session_id?)]
	SP -->|accessor| SPM2[get_named_service(type, name, session_id?)]
	SP -->|accessor| SPM3[get_all_named_services(type, session_id?)]
	SP -->|introspection| SPM4[get_all_services() / get_services_by_type() / get_service_types() / has_service()]
	SP -->|session lifecycle| SPM5[dispose_session() / clear_all_sessions()]
	SP -->|instance lifecycle| SPM6[clear_singleton_instances() / clear_all_instances()]
	SP -->|registration mutation| SPM7[remove_service() / remove_all_by_type() / remove_all_by_implementation()]

	SPM1 --> L1[Singleton cache]
	SPM1 --> L2[Transient creation]
	SPM1 --> L3[Scoped context manager]

	L2 --> SESS[Session store + timeout cleanup]
	L3 --> SCM[ScopedServiceContextManager]
```

## Architecture Notes For Copilot
- Core entry point is `ApplicationBuilder`; container access is through `ServiceProvider`.
- `ApplicationBuilder` always ensures a default `IConfiguration` registration exists unless replaced.
- `ServiceProvider` is a singleton container instance with cached singletons and optional session-scoped transient reuse.
- Scoped resolutions return a context-manager wrapper for direct access, while dependency-injected scoped instances are unwrapped internally.
- Session cleanup and disposal paths are explicit and part of the public surface.

## Entry And Accessor Method Index

### Entry Methods (`ApplicationBuilder`)
- `configure_services(callback)`
- `configure_configuration(config_action)`
- `use_configuration(configuration)`
- `build()`

### Accessor Methods (`ServiceProvider`)
- `get_service(service_type, session_id=None)`
- `get_named_service(service_type, name, session_id=None)`
- `get_all_named_services(service_type, session_id=None)`
- `get_all_services()`
- `get_services_by_type(service_type=None)`
- `get_service_types()`
- `has_service(service_type, name=None)`

### Lifecycle/State Accessors (`ServiceProvider`)
- `get_session_info(session_id)`
- `get_active_session_count()`
- `dispose_session(session_id)`
- `clear_singleton_instances()`
- `clear_all_sessions()`
- `clear_all_instances()`

## Forward Direction
- The core purpose and design are complete.
- Prioritize enhancements, detail completion, and bug fixes.
- Propose non-core capabilities as separate packages that integrate with this package.

## Testing Requirements
- Use a four-stage test strategy:
	1. Unit tests for individual components and methods.
	2. Integration tests for overall package behavior.
	3. End-to-end tests for complete workflows.
	4. Performance and stress tests for scalability and reliability.
- Testing stack is fixed: `pytest` plus Python standard library tools.
- Do not add extra testing dependencies.
- Follow TDD for fixes and enhancements:
	1. Add/adjust tests first.
	2. Implement the change.
	3. Verify tests document expected behavior.

## Documentation Sync
- For behavioral changes, review `README.md`.
- If public API or expected behavior changes, update `README.md` in the same change.

## Python Coding Conventions
- Follow PEP 8.
- Use type hints for all public methods and functions.
- Include Google-style docstrings for all public classes and methods.
- Avoid global state and mutable default arguments.
- Prefer context managers, pipelines, and functional style where it improves clarity.
- Keep modules cohesive with clear responsibilities.
- Avoid unnecessary abstractions and over-engineering.
- Prioritize in this order:
	1. Correctness
	2. Readability
	3. Maintainability
	4. Performance

## Hard Constraints
- Do not add dependencies beyond the Python standard library.
- Do not modify core logic or architecture without clear justification.
- Do not modify core logic or architecture without user confirmation.

## Response Style
- Keep explanations brief.
- Focus on clear, direct implementation.
- Provide deeper justification only when requested.