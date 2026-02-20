from setuptools import setup, find_packages
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="nano-crucible",
    version="2.0.0",
    author="mkywall",
    author_email="mkywall3@gmail.com",
    description="Python Client for Crucible - National Archive for NSRC Observations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="BSD",
    url="https://github.com/MolecularFoundryCrucible/nano-crucible",

    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "pytz>=2021.1",
        "ipywidgets",
        "pydantic",
        "python-dotenv",
        "argcomplete>=2.0.0",
        "platformdirs>=2.5.0"
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.812",
        ],
    },
    entry_points={
        'console_scripts': [
            'crucible=crucible.cli:main',
        ],
    },
)
