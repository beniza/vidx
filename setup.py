from setuptools import setup, find_packages

setup(
    name="vidx",
    version="0.2.0",
    packages=find_packages(),
    install_requires=[
        "pyyaml>=5.4.1",
    ],
    extras_require={
        "test": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "vidx=vidx.cli:main",
        ],
    },
    description="Scripture video rendering companion engine to audx (combining USFM files, timing maps, audio, and FFmpeg).",
    author="Bridgeconn",
    python_requires=">=3.7",
)
