# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'CodeMate'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'CodeMate'
copyright = '2024-2026, Sebastian Januchowski'
author = 'Sebastian Januchowski'
release = '4.0'
version = '4.0'
license = 'Freeware'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
]

# The root index page is a language selector; each language tree has its own
# index. The shared API reference stays at the source root and is linked from
# both trees.
root_doc = 'index'
locale_dirs = ['locale/']
gettext_compact = False

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Language versions --------------------------------------------------------
# Each language lives in its own subdirectory (en/, pl/). English is the
# primary language and is listed first; the "current" version gets no link.

DOC_LANGUAGES = [
    ('en', 'English'),
    ('pl', 'Polski'),
]
DOC_DEFAULT_LANG = 'en'


def _lang_switch_context(app, pagename, templatename, context, doctree):
    """Provide ``lang_switch`` to every template: (code, name, url|None)."""
    # Detect the language of the current page from its source path.
    current = DOC_DEFAULT_LANG
    for code, _name in DOC_LANGUAGES:
        if pagename.startswith(code + '/') or pagename == code:
            current = code
            break
    switch = []
    for code, name in DOC_LANGUAGES:
        if code == current:
            switch.append((code, name, None))
            continue
        # Map e.g. 'pl/usage' -> 'en/usage', 'index' -> '<other>/index'
        if '/' in pagename:
            sibling = code + '/' + pagename.split('/', 1)[1]
        else:
            sibling = code + '/' + pagename
        if sibling in app.env.all_docs:
            switch.append((code, name, app.builder.get_relative_uri(pagename, sibling)))
        else:
            # Fall back to the language's index page.
            fallback = code + '/index'
            if fallback in app.env.all_docs:
                switch.append((code, name, app.builder.get_relative_uri(pagename, fallback)))
            else:
                switch.append((code, name, None))
    context['lang_switch'] = switch
    context['current_lang'] = current

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_css_files = [
    'custom.css',
]

# -- Extension configuration -------------------------------------------------

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Autodoc settings
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}


def setup(app):
    # Inject the language switcher links into every page's template context.
    app.connect('html-page-context', _lang_switch_context)
