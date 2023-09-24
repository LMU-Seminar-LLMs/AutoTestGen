from typing import Union, Type
from . import language_adapters

# API CONFIGURATION
API_KEY: Union[str, None] = None
ORG_KEY: Union[str, None] = None
MODEL: str = "gpt-3.5-turbo" # DEFAULT MODEL

# AutoTestGen CONFIGURATION
ADAPTER: Type[language_adapters.BaseAdapter] = None