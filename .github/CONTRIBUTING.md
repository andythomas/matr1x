# How to contribute to Matr1x

### Did you find a bug or have a suggestion for improvement?

If you find a bug:

1. Check if the issue already exists on [GitHub](https://github.com/andythomas/matr1x/issues)
2. If not, create an issue using the bug template.
3. Follow the instructions and hints on the bug template.

### Submitting Pull Requests

1. Fork the repository.
2. Create a new branch for your changes.
3. Make your changes and commit them with clear, descriptive messages.
4. Format the code with `ruff format` and check it with `ruff check` and `ty check`.
5. Ensure the new code passes the test suite: `pytest`.
6. Push to your fork and submit a pull request.

### Development Setup

Make sure your installation has all the required dependencies.

```bash
uv sync --all-extras --all-groups
```

### Code Style

- Use meaningful variable and function names
- Add docstrings to functions and classes in numpy format
- Keep functions focused and concise
- The exact style guide is enforced by `ruff`.

## Questions?

Please open an issue for questions or discussions about contributing.
