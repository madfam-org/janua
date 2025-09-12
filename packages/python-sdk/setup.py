from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="plinto",
    version="0.1.0",
    author="Plinto Team",
    author_email="support@plinto.dev",
    description="Official Python SDK for Plinto - Modern authentication and user management platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/plinto/plinto",
    project_urls={
        "Bug Tracker": "https://github.com/plinto/plinto/issues",
        "Documentation": "https://docs.plinto.dev",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    packages=["plinto"],
    python_requires=">=3.7",
    install_requires=[
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
        "python-jose[cryptography]>=3.3.0",
        "python-dateutil>=2.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "ruff>=0.1.0",
        ],
        "django": [
            "django>=3.2",
        ],
        "fastapi": [
            "fastapi>=0.100.0",
        ],
        "flask": [
            "flask>=2.0.0",
        ],
    },
)