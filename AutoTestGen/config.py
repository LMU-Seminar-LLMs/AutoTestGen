from typing import Union, Type
from . import language_adapters

# API CONFIGURATION
API_KEY: Union[str, None] = None
ORG_KEY: Union[str, None] = None
MODEL: Union[str, None] = None

# AutoTestGen CONFIGURATION
ADAPTER: Type[language_adapters.BaseAdapter] = None