import unittest
from unittest.mock import patch
from AutoTestGen.utils import config
from AutoTestGen.utils import (
    compute_coverage,
    find_lines,
    _retrieve_source
)

class TestComputeCoverage(unittest.TestCase):
    
    @patch('AutoTestGen.utils.find_lines')
    def test_empty_test_metadata(self, mock_find_lines):
        mock_find_lines.return_value = (1, 10, None)
        result = compute_coverage("object_name", "function", [])
        self.assertEqual(result, 0)
    
    @patch('AutoTestGen.utils.find_lines')
    def test_function_coverage(self, mock_find_lines):
        mock_find_lines.return_value = (1, 10, None)
        test_metadata = [
            {"executed_lines": [1, 2, 3, 4], "missing_lines": [5, 6]},
            {"executed_lines": [1, 2, 3, 4, 5], "missing_lines": [6]},
            {"executed_lines": [1, 2, 3, 4, 5, 6], "missing_lines": []}
        ]
        result = compute_coverage("object_name", "function", test_metadata)
        self.assertEqual(result, 100)
    
    @patch('AutoTestGen.utils.find_lines')
    def test_class_coverage(self, mock_find_lines):
        mock_find_lines.return_value = (1, 10, None)
        test_metadata = [
            {"executed_lines": [1, 2, 3, 4], "missing_lines": [5, 6]},
            {"executed_lines": [1, 2, 3, 4, 5], "missing_lines": [6]},
            {"executed_lines": [1, 2, 3, 4, 5, 6], "missing_lines": []}
        ]
        result = compute_coverage("object_name", "class", test_metadata)
        self.assertEqual(result, 100)
    
    @patch('AutoTestGen.utils.find_lines')
    def test_class_method_coverage(self, mock_find_lines):
        mock_find_lines.return_value = (1, 10, None)
        test_metadata = [
            {"executed_lines": [1, 2, 3, 4], "missing_lines": [5, 6]},
            {"executed_lines": [1, 2, 3, 4, 5], "missing_lines": [6]},
            {"executed_lines": [1, 2, 3, 4, 5, 6], "missing_lines": []}
        ]
        result = compute_coverage(
            "object_name",
            "class method",
            test_metadata,
            "class_name"
        )
        self.assertEqual(result, 100)

class TestFindLines(unittest.TestCase):
    
    def setUp(self):
        config.ADAPTER = MockAdapter()
    
    def test_find_lines_function(self):
        start_line, end_line, source_code = find_lines(
            "my_function",
            "function"
        )
        self.assertEqual(start_line, 1)
        self.assertEqual(end_line, 5)
        self.assertEqual(source_code, [
            "def my_function():",
            "    print('Hello, world!')",
            "    print('This is a test function.')",
            "    print('Goodbye!')",
            ""
        ])
    
    def test_find_lines_class(self):
        start_line, end_line, source_code = find_lines("MyClass", "class")
        self.assertEqual(start_line, 6)
        self.assertEqual(end_line, 19)
        self.assertEqual(source_code, [
            "class MyClass:",
            "    def __init__(self):",
            "        self.name = 'John'",
            "        self.age = 30",
            "",
            "    def greet(self):",
            "        print(f'Hello, my name is {self.name}')",
            "    ",
            "    @classmethod",
            "    def my_method(cls):",
            "        print('This is a class method.')",
            "        print('It belongs to the MyClass class.')",
            "        print('Goodbye!')",
            ""
        ])
    
    def test_find_lines_class_method(self):
        start_line, end_line, source_code = find_lines(
            "my_method",
            "class method",
            class_name="MyClass"
        )
        self.assertEqual(start_line, 14)
        self.assertEqual(end_line, 19)
        self.assertEqual(source_code, [
            "    @classmethod",
            "    def my_method(cls):",
            "        print('This is a class method.')",
            "        print('It belongs to the MyClass class.')",
            "        print('Goodbye!')",
            ""
        ])
    
    def test_find_lines_adapter_not_set(self):
        config.ADAPTER = None
        with self.assertRaises(ValueError):
            find_lines("my_function", "function")
    
    def test_find_lines_invalid_object_type(self):
        with self.assertRaises(ValueError):
            find_lines("my_function", "invalid_type")
    
    def test_retrieve_source_function(self):
        source_code = _retrieve_source("my_function", "function")
        self.assertEqual(
            source_code,
            (
                "def my_function():\n"
                "    print('Hello, world!')\n"
                "    print('This is a test function.')\n"
                "    print('Goodbye!')\n"
            )
        )
    
    def test_retrieve_source_class(self):
        source_code = _retrieve_source("MyClass", "class")
        self.assertEqual(
            source_code,
            (
                "class MyClass:\n"
                "    def __init__(self):\n"
                "        self.name = 'John'\n"
                "        self.age = 30\n\n"
                "    def greet(self):\n"
                "        print(f'Hello, my name is {self.name}')\n    \n"
                "    @classmethod\n"
                "    def my_method(cls):\n"
                "        print('This is a class method.')\n"
                "        print('It belongs to the MyClass class.')\n"
                "        print('Goodbye!')\n"
            )
        )
    
    def test_retrieve_source_class_method(self):
        source_code = _retrieve_source(
            "my_method",
            "class method",
            class_name="MyClass"
        )
        self.assertEqual(
            source_code,
            (
                "    @classmethod\n"
                "    def my_method(cls):\n"
                "        print('This is a class method.')\n"
                "        print('It belongs to the MyClass class.')\n"
                "        print('Goodbye!')\n"
            )
        )

class MockAdapter:
    
    def retrieve_module_source(self):
        return """def my_function():
    print('Hello, world!')
    print('This is a test function.')
    print('Goodbye!')

class MyClass:
    def __init__(self):
        self.name = 'John'
        self.age = 30

    def greet(self):
        print(f'Hello, my name is {self.name}')

    @classmethod
    def my_method(cls):
        print('This is a class method.')
        print('It belongs to the MyClass class.')
        print('Goodbye!')
"""
    
    def retrieve_func_source(self, object_name):
        if object_name == "my_function":
            return """def my_function():
    print('Hello, world!')
    print('This is a test function.')
    print('Goodbye!')
"""
    
    def retrieve_class_source(self, object_name):
        if object_name == "MyClass":
            return """class MyClass:
    def __init__(self):
        self.name = 'John'
        self.age = 30

    def greet(self):
        print(f'Hello, my name is {self.name}')
    
    @classmethod
    def my_method(cls):
        print('This is a class method.')
        print('It belongs to the MyClass class.')
        print('Goodbye!')
"""
    
    def retrieve_classmethod_source(self, class_name, method_name):
        if class_name == "MyClass" and method_name == "my_method":
            return """    @classmethod
    def my_method(cls):
        print('This is a class method.')
        print('It belongs to the MyClass class.')
        print('Goodbye!')
"""
