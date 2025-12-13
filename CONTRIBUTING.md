# Contributing to servicegraph

## Getting Started

### Development Setup
```bash
git clone https://github.com/your-org/servicegraph.git
cd servicegraph
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

### Running Tests
```bash
pytest                    # Run all tests
pytest -v                # Verbose output
pytest --cov=servicegraph        # With coverage report
pytest -m "not slow"     # Skip slow tests
```

### Code Quality
```bash
black src/ tests/        # Format code
isort src/ tests/        # Sort imports
mypy src/                # Type checking
```

## Contribution Guidelines

### Pull Request Process
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass and coverage remains >95%
6. Update documentation if needed
7. Commit with clear messages
8. Push and create a Pull Request

### Code Standards

**Maintaining Consistency and Quality**

This project uses automated tools to enforce standards, allowing contributors to focus on solving problems rather than debating formatting conventions.

**Automated Enforcement**
- **Black** formats all code automatically
- **isort** organizes imports consistently
- **mypy** enforces type safety
- **pytest** validates coverage remains >95%

If these tools pass, the code meets the formatting standards.

**Required Practices**
- Add type hints to all functions and methods
- Write clear docstrings for public APIs
- Include tests for new functionality (with edge cases)
- Maintain code readability—favor clarity over cleverness
- No external dependencies for core functionality (see Development Philosophy in README)

**Code Review Focus**

Reviews concentrate on substance:
- ✅ Correctness and edge case handling
- ✅ Test coverage and quality
- ✅ API design and maintainability
- ✅ Code readability and clarity
- ✅ Performance implications
- ✅ Documentation completeness

Reviews do not focus on:
- ❌ Formatting (Black handles this)
- ❌ Import ordering (isort handles this)
- ❌ Style preferences when existing patterns are sound

**Philosophy**: Automation removes subjectivity from formatting decisions, enabling contributors to concentrate on building robust, maintainable solutions. Clear, readable code that solves real problems is the goal.

### Commit Message Format
```
type(scope): brief description

Detailed explanation if needed

Fixes #issue-number
```

Types: feat, fix, docs, style, refactor, test, chore

## License Agreement
By contributing, you agree that your contributions will be licensed under the Apache 2.0 with Commons Clause license.

## Questions?
Open an issue or discussion on GitHub.
