from setuptools import setup, find_packages

setup(
    name="vidx",
    version="0.1.0-alpha",
    packages=find_packages(),
    install_requires=[
        "pyyaml>=5.4.1",
        "usfm-converter>=0.1.1a0"
    ],
    entry_points={
        "console_scripts": [
            "vidx=vidx.cli:main",
        ],
    },
    description="Scripture video rendering companion engine to audx (combining USFM files, timing maps, audio, and FFmpeg).",
    author="Bridgeconn",
    python_requires=">=3.7",
)
