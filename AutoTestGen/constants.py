from typing import Type
from . import language_adapters

# Supported Models
MODELS: list[str] = [
    'gpt-3.5-turbo',
    'gpt-3.5-turbo-16k',
    'gpt-4',
    'gpt-4-32k'
]

# Adapter Registry
ADAPTERS: dict[str, Type[language_adapters.BaseAdapter]] = {
    "python": language_adapters.PythonAdapter,
    "r": language_adapters.RAdapter,
    "java": language_adapters.JavaAdapter
}

# Language file suffixes
SUFFIXES: dict[str, str] = {
    "python": ".py",
    "r": ".r",
    "java": ".java"
}