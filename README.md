<p align="center">
    <img src="data/readme/logo.jpg" height="auto" style="width: 25%" onerror="this.onerror=null;this.src='_static/logo.jpg'" />
</p>

<h1 align="center">The Luxury Python Template</h1>

<p align="center">
    <img src="https://img.shields.io/badge/build-passed-brightgreen" />
    <img src="https://img.shields.io/badge/test-passed-brightgreen" />
    <img src="https://img.shields.io/badge/test_coverage-100%25-brightgreen" />
    <img src="https://img.shields.io/badge/doc_coverage-100%25-brightgreen" />
    <img src="https://img.shields.io/badge/vulnerabilities-0-brightgreen" />
    <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" /></a>
</p>

<h4 align="center">Maximum Coding Convenience from Day One</h4>

<p align="center">
    <a href="#introduction">Introduction</a> •
    <a href="#example-report">Example Report</a> •
    <a href="#quick-guide">Quick Guide</a>
</p>
<br />

# Introduction
There are great tools available to automatically style, analyze, and build your code. 
They help you deliver better products faster. However, you have to learn how they work, 
configure them, and clean up after them. It’s easy to forgo this tedious work in the 
beginning when all you can think about is the bright idea behind your new Python 
package. Will you do that later on? Probably not, because then chances are high that you 
get hundreds of complaints from these tools, and fixing them all will likely set you back 
for weeks. It's way more fun to focus on new features anyway.  <br />

Writing better code would be so much easier if any new project, regardless of whether it 
starts out as an afternoon experiment or the next big thing, already included all 
of the bells and whistles that professional packages use. For free and without having to 
register yourself for yet another online service.  <br />

With the luxury Python template, you can have all that right from the start! It is very 
opinionated, meaning the only thing you have to think about is the project name. It 
comes with a single, zero-configuration command-line tool. Its options are intentionally 
limited and therefore easy to remember. 

# Requirements
- Python 3.9 or higher
- [uv package manager](https://docs.astral.sh/uv/)

# Quick Guide
You get everything with a single call of:
```Shell
uv run package.py build
```
That's it! You don't even have to create a virtual environment. The above command 
takes care of that. It performs the following tasks for you:

- Creating a virtual environment.
- Installing all needed dependencies.
- Formatting and linting your code with [ruff](https://docs.astral.sh/ruff/).
- Static type analysis with [MyPy](https://github.com/python/mypy).
- Checking for security issues with [Bandit](https://github.com/PyCQA/bandit).
- Running tests with [Pytest](https://docs.python.org/3/library/unittest.html) and 
evaluating test coverage with [Coverage.py](https://github.com/nedbat/coveragepy)
- Generating documentation with [Sphinx](https://www.sphinx-doc.org/en/master/) and 
markdown support from [MySt](https://myst-parser.readthedocs.io/en/latest/).
- Checking for undocumented code (built into `package.py`).
- Generating a single, beautiful report for all of the above with [Pico.css](https://picocss.com/).
- Building wheel files and incrementing the version number according to 
[calendar versioning](https://calver.org/).
- Generating badges with the most important metrics for your repository like the ones 
shown above using [shields.io](https://shields.io/)
- Removing temporary files and folders.

## Specialized Commands

**Report Only** - Generate the report without building the package:
```Shell
uv run package.py report
```

**Documentation Only** - Generate the documentation without building the package or 
generating a report:
```Shell    
uv run package.py doc
```

**Remove Generated Files** - Remove all generated files and folders including the wheel 
files, documentation, and 
report:
```Shell
uv run package.py remove
```

**Get Help** - If you want to see all available commands and options, run:

```Shell
uv run package.py --help
```

# Example Report
The `package.py` tool that comes with the template can generate a single, 
beautiful report that summarizes the results of the above-mentioned tools. Want an example?
Have a look at the following, problematic code:

```python
import hashlib
import subprocess

from django.db.models import Model


def getHash(password: str):
    """
    This is an example function for encrypting passwords.

    Args:
        password: The password to be encrypted.
    """

    return hashlib.md5(str(password).encode("utf-8"))


print(getHash(12345))
```

In this example, the code is stored in `src/bad_example.py`. If you run 
`python package.py build` you will get the report. 
[Have a look!](https://woernerm.github.io/luxury_python_template/)

# Supported Package Managers
The luxury Python template supports the super-fast [uv](https://docs.astral.sh/uv/). 
Pip is no longer supported, because the author of this template got tired of waiting for 
the virtual environment to be created. Yes, the template is very opinionated 😉.

# License
The package is distributed under Apache License 2.0. You can use it for anything you 
want! Attribution would be nice, but you do not have to.
