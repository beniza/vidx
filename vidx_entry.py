"""
Entry point script for PyInstaller executable bundling.
Ensures the vidx package is loaded as a module so relative imports resolve correctly.
"""
from vidx.cli import main

if __name__ == "__main__":
    main()
