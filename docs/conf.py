import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'ReLove Communication Bot'
copyright = '2024, ReLove Team'
author = 'ReLove Team'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_rtd_theme',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'aiogram': ('https://docs.aiogram.dev/en/latest/', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org/en/latest/', None),
}

autodoc_member_order = 'bysource'
add_module_names = False 