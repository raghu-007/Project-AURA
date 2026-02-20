"""Setup configuration for Project-AURA."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="project-aura",
    version="0.1.0",
    author="Raghu S",
    description="AI multi-agent ecosystem simulation with emergent behaviors",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/raghu-007/Project-AURA",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "aura=aura.__main__:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Artificial Life",
    ],
)
