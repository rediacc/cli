# PyPI Publishing Guide for Rediacc

This guide explains how to build and publish the Rediacc CLI package to PyPI (Python Package Index) or TestPyPI for testing.

## Prerequisites

1. **Python 3.8+** installed
2. **PyPI Account**: Create accounts at:
   - TestPyPI (for testing): https://test.pypi.org/account/register/
   - PyPI (for production): https://pypi.org/account/register/
3. **API Tokens**: Generate API tokens for authentication:
   - TestPyPI: https://test.pypi.org/manage/account/token/
   - PyPI: https://pypi.org/manage/account/token/

## Project Structure

The package is configured using modern Python packaging standards:

```
cli/
├── pyproject.toml        # Package configuration and metadata
├── MANIFEST.in          # Specifies additional files to include
├── src/
│   └── cli/
│       ├── __init__.py
│       ├── _version.py  # Centralized version management
│       ├── __main__.py  # Module execution support
│       ├── commands/    # CLI command modules
│       ├── core/        # Core functionality
│       └── gui/         # GUI components
└── scripts/
    └── build-pypi.py    # Build and publish script
```

## Building the Package

### Using the Build Script (Recommended)

The `scripts/build-pypi.py` script automates the entire build process:

```bash
# Basic build (creates wheel and source distribution)
cd cli
python scripts/build-pypi.py 0.1.0

# Build and upload to TestPyPI
python scripts/build-pypi.py 0.1.0 --upload testpypi --token YOUR_TEST_TOKEN

# Build and upload to PyPI (production)
python scripts/build-pypi.py 0.1.0 --upload pypi --token YOUR_PYPI_TOKEN
```

### Manual Build Process

If you prefer to build manually:

```bash
cd cli

# Install build tools (packaging>=24.1 required for PEP 639 support)
pip install build twine "packaging>=24.1"

# Update version in src/cli/_version.py
# Edit the file and change __version__ = "0.1.0"

# Clean previous builds
rm -rf build dist *.egg-info

# Build the package
python -m build

# Check the package
python -m twine check dist/*
```

## Publishing to TestPyPI (Testing)

TestPyPI is a separate instance of PyPI for testing packages before production release.

### 1. Build and Upload

```bash
# Using the script
python scripts/build-pypi.py 0.1.0 --upload testpypi --token YOUR_TEST_TOKEN

# Or manually
python -m twine upload --repository testpypi dist/*
```

### 2. Test Installation

```bash
# Create a test virtual environment
python -m venv test-env
source test-env/bin/activate  # On Windows: test-env\Scripts\activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            rediacc

# Test the installation
rediacc --version
rediacc-sync --help
rediacc-term --help
```

### 3. Verify Entry Points

All console scripts should be available:
- `rediacc` - Main CLI interface
- `rediacc-sync` - File synchronization
- `rediacc-term` - Terminal access
- `rediacc-plugin` - Plugin management
- `rediacc-workflow` - Workflow execution
- `rediacc-gui` - GUI application

## Publishing to PyPI (Production)

Once testing is complete, publish to the production PyPI:

### 1. Update Version

Ensure the version number follows semantic versioning (MAJOR.MINOR.PATCH):

```python
# src/cli/_version.py
__version__ = "1.0.0"  # Production release
```

### 2. Build and Upload

```bash
# Using the script
python scripts/build-pypi.py 1.0.0 --upload pypi --token YOUR_PYPI_TOKEN

# Or manually
python -m build
python -m twine upload dist/*
```

### 3. Installation

Users can now install directly from PyPI:

```bash
pip install rediacc

# Or with GUI support
pip install rediacc[gui]

# Or for development
pip install rediacc[dev]
```

## Version Management

### Semantic Versioning

Follow semantic versioning conventions:
- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

Examples:
- `0.1.0` - Initial development release
- `0.2.0` - New features added
- `0.2.1` - Bug fixes
- `1.0.0` - First stable release

### Pre-release Versions

For alpha/beta releases:
```python
__version__ = "1.0.0a1"  # Alpha 1
__version__ = "1.0.0b1"  # Beta 1
__version__ = "1.0.0rc1" # Release Candidate 1
```

## Configuration Files

### pyproject.toml

The main configuration file defining:
- Build system requirements
- Package metadata (name, description, authors)
- Dependencies and optional dependencies
- Console script entry points
- PyPI classifiers

### MANIFEST.in

Specifies additional files to include in the distribution:
- Documentation files
- Configuration JSON files
- License and README

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   ```
   Solution: Use API tokens, not username/password
   Format: Username: __token__
          Password: YOUR_API_TOKEN
   ```

2. **Version Already Exists**
   ```
   Solution: Increment version number in _version.py
   ```

3. **Missing Dependencies**
   ```
   Solution: Ensure all dependencies are listed in pyproject.toml
   ```

4. **Import Errors After Installation**
   ```
   Solution: Check MANIFEST.in includes all necessary files
   ```

### Validation Checklist

Before publishing:
- [ ] Version number updated in `_version.py`
- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] Package builds without errors
- [ ] Package validation passes (`twine check`)
- [ ] Test installation from TestPyPI works
- [ ] All console scripts functional

## Automation with CI/CD

### GitHub Actions Example

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install build twine "packaging>=24.1"
    - name: Build package
      run: python -m build
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: python -m twine upload dist/*
```

## Security Considerations

1. **Never commit API tokens** to version control
2. **Use environment variables** for tokens in CI/CD
3. **Generate scoped tokens** for specific projects
4. **Rotate tokens regularly**
5. **Test on TestPyPI first** before production release

## Links and Resources

- **PyPI**: https://pypi.org/
- **TestPyPI**: https://test.pypi.org/
- **Python Packaging Guide**: https://packaging.python.org/
- **Setuptools Documentation**: https://setuptools.pypa.io/
- **Twine Documentation**: https://twine.readthedocs.io/
- **Build Documentation**: https://pypa-build.readthedocs.io/

## Support

For issues or questions about publishing:
1. Check the [Python Packaging User Guide](https://packaging.python.org/)
2. Review [PyPI Help](https://pypi.org/help/)
3. Contact the Rediacc development team