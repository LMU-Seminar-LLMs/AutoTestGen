from .base_adapter import BaseAdapter

class JavaAdapter(BaseAdapter):
    def __init__(self, testing_framework="JUnit"):
        super().__init__(testing_framework)