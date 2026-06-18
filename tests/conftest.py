# -*- coding: utf-8 -*-
import sys
import os

# Add project root and venv site-packages to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_site = os.path.join(project_root, "venv", "Lib", "site-packages")
sys.path.insert(0, project_root)
if os.path.exists(venv_site):
    sys.path.insert(0, venv_site)