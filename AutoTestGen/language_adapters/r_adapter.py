from .base_adapter import BaseAdapter

class RAdapter(BaseAdapter):
    def __init__(self, testing_framework="testthat"):
        super().__init__(testing_framework)