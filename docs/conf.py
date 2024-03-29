# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import importlib

sys.path.append(os.path.abspath("../"))


# -- Project information -----------------------------------------------------
packagemod = importlib.import_module("package", "..")
meta = packagemod.Meta("../pyproject.toml")

project = meta.get("name")
copyright = meta.getCopyright()
author = ", ".join(meta.getAuthors())

# The full version, including alpha/beta/rc tags
release = meta.get("version")
packagesettings = packagemod.Settings()

sys.path.append(os.path.abspath(packagesettings.SRC_DIR))


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",  # Automatic API documentation
    "sphinx.ext.napoleon",  # Google-style docstrings
    "myst_parser",  # Import markdown files like Readme.md.
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pydata_sphinx_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []

# Add any MyST extension names here, as strings.
myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_image",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

autodoc_default_options = {
    "member-order": "groupwise",
    "special-members": "__init__",
    "undoc-members": False,
}


def setup(app):
    docinspect = packagemod.DocInspector(packagesettings)
    app.connect("autodoc-process-docstring", docinspect.process)
    app.connect("build-finished", docinspect.finish)
