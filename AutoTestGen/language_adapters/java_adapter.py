from .base_adapter import BaseAdapter

class JavaAdapter(BaseAdapter):
    def __init__(self, module: str):
        super().__init__("java", module)