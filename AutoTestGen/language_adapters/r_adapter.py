from .base_adapter import BaseAdapter

class RAdapter(BaseAdapter):
    def __init__(self, module: str):
        super().__init__("r", module)