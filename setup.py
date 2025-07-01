from setuptools import setup, find_packages
from setuptools.command.install import install
import subprocess
import sys

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        # Устанавливаем spaCy модель
        subprocess.check_call([sys.executable, "scripts/install_spacy_model.py"])

setup(
    name="relove_bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiogram==3.3.0",
        "aiohttp==3.9.3",
        "pydantic==2.6.1",
        "pydantic-settings==2.1.0",
        "python-json-logger==2.0.7",
        "python-dotenv==1.0.1",
        "tqdm==4.66.1",
        "sqlalchemy[asyncio]==2.0.27",
        "asyncpg==0.29.0",
        "alembic==1.13.1",
        "psycopg2-binary==2.9.9",
        "redis==5.0.1",
        "aioredis==2.0.1",
        "python-telegram-bot==20.7",
        "telethon==1.33.1",
        "torch==2.2.0",
        "transformers==4.37.2",
        "accelerate==0.26.1",
        "bitsandbytes==0.41.3",
        "peft==0.7.1",
        "sentencepiece==0.1.99",
        "spacy==3.7.2",
        "websockets==12.0",
        "python-multipart==0.0.6",
        "aiofiles==23.2.1",
        "pandas==2.2.0",
        "numpy==1.26.3",
        "plotly==5.18.0",
        "dash==2.14.2",
        "dash-bootstrap-components==1.5.0",
        "openpyxl==3.1.2",
        "xlrd==2.0.1",
        "pytest==8.0.0",
        "pytest-asyncio==0.23.5",
        "pytest-cov==4.1.0",
        "sphinx==7.2.6",
        "sphinx-rtd-theme==2.0.0",
    ],
    cmdclass={
        'install': PostInstallCommand,
    },
    python_requires=">=3.9",
    author="ReLove Team",
    author_email="your-email@example.com",
    description="Telegram bot for psychological diagnostics and platform integration",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/relove_communication_bot",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 