import os
import sys

# Ensure the package can be imported for AutoAPI's import resolution
sys.path.insert(0, os.path.abspath("../../xboinc"))

# -- Project information -----------------------------------------------------
project = "Xboinc"
author = (
    "Frederik F. Van der Veken, Carlo E. Montanari, Davide Di Croce, Giovanni Iadorala"
)
copyright = f"2025, {author}"
release = "0.4.1"
version = release

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx.ext.mathjax",
    "myst_parser",
    "autoapi.extension",
]

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True

# Intersphinx mappings
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
}

typehints_fully_qualified = False
always_document_param_types = True

templates_path = ["_templates"]
exclude_patterns = []

# -- HTML output -------------------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
}
html_title = f"{project} v{release}"
add_module_names = False

# -- AutoAPI configuration ---------------------------------------------------
autoapi_type = "python"
autoapi_dirs = ["../../xboinc"]
autoapi_root = "api"
autoapi_add_toctree_entry = True
autoapi_keep_files = True
