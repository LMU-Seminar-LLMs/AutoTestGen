import unittest
from types import ModuleType
import inspect
import ast
from AutoTestGen.language_adapters.python_adapter import (
    _is_method,
    _has_init,
    _is_class,
    _get_init,
    _trace_module,
    _trace_call,
    _get_function_name,
)

class TestIsMethod(unittest.TestCase):
    def test_is_method(self):
        class MyClass:
            def my_method(self): pass
        
        module = ModuleType("test_module")
        setattr(module, "MyClass", MyClass)
        
        self.assertTrue(_is_method("MyClass.my_method", module))
        self.assertFalse(_is_method("MyClass.nonexistent_method", module))
        self.assertFalse(_is_method("NonexistentClass.my_method", module))
        self.assertFalse(_is_method("NonexistentClass.nonexistent_method", module))
        self.assertFalse(_is_method("MyClass", module))
        self.assertFalse(_is_method("NonexistentClass", module))

class TestHasInit(unittest.TestCase):
    def test_has_init_with_init_method(self):
        class TestClass:
            def __init__(self): pass
        
        sourced_module = ModuleType("sourced_module")
        setattr(sourced_module, "TestClass", TestClass)
        
        self.assertTrue(_has_init("TestClass", sourced_module))
    
    def test_has_init_without_init_method(self):
        class TestClass: pass

        sourced_module = ModuleType("sourced_module")
        setattr(sourced_module, "TestClass", TestClass)
        self.assertFalse(_has_init("TestClass", sourced_module))
    
    def test_has_init_with_invalid_class_name(self):
        sourced_module = ModuleType("sourced_module")
        self.assertFalse(_has_init("InvalidClass", sourced_module))

class TestIsClass(unittest.TestCase):
    
    def test_existing_class(self):
        class MyClass: pass
        module = ModuleType("test_module")
        setattr(module, "MyClass", MyClass)
        self.assertTrue(_is_class("MyClass", module))
    
    def test_non_existing_class(self):
        module = ModuleType("test_module")
        self.assertFalse(_is_class("MyClass", module))
    
    def test_nested_class(self):
        class MyParentClass:
            class MyChildClass: pass
        module = ModuleType("test_module")
        setattr(module, "MyParentClass", MyParentClass)
        self.assertTrue(_is_class("MyParentClass.MyChildClass", module))
    
    def test_nested_non_existing_class(self):
        class MyParentClass: pass
        module = ModuleType("test_module")
        setattr(module, "MyParentClass", MyParentClass)
        self.assertFalse(_is_class("MyParentClass.MyChildClass", module))

class TestGetInit(unittest.TestCase):

    def test_get_init_with_valid_input(self):
        class TestClass:
            def __init__(self): pass

        sourced_module = ModuleType('test_module')
        setattr(sourced_module, 'TestClass', TestClass)

        result = _get_init('TestClass', sourced_module)
        expected_result = inspect.getsource(TestClass.__init__)
        self.assertEqual(result, expected_result)

    def test_get_init_with_no_init(self):
        class TestClass:
            pass

        sourced_module = ModuleType('test_module')
        setattr(sourced_module, 'TestClass', TestClass)

        result = _get_init('TestClass', sourced_module)
        self.assertIsNone(result)

    def test_get_init_with_invalid_call_name(self):
        class TestClass:
            def __init__(self): pass

        sourced_module = ModuleType('test_module')
        setattr(sourced_module, 'TestClass', TestClass)

        with self.assertRaises(AttributeError):
            _get_init('InvalidClassName', sourced_module)

    def test_get_init_with_invalid_module(self):
        class TestClass:
            def __init__(self): pass

        sourced_module = ModuleType('test_module')

        with self.assertRaises(AttributeError):
            _get_init('TestClass', sourced_module)

class TestTraceModule(unittest.TestCase):
    def setUp(self):
        self.module = ModuleType("test_module")
        self.submodule1 = ModuleType("submodule1")
        self.submodule2 = ModuleType("submodule2")

        setattr(self.module, 'submodule1', self.submodule1)
        setattr(self.submodule1, 'submodule2', self.submodule2)

    def test_trace_module(self):
        result = _trace_module("submodule1.submodule2", self.module)
        self.assertEqual(result, self.submodule2)

    def test_trace_module_no_submodules(self):
        result = _trace_module("", self.module)
        self.assertEqual(result, self.module)

    def test_trace_module_invalid_module(self):
        with self.assertRaises(AttributeError):
            _trace_module("invalid_submodule", self.module)

class TestTraceCall(unittest.TestCase):
    
    def test_trace_call(self):
        sourced_module = ModuleType("test_module")
        setattr(sourced_module, "func", lambda x: x + 1)
        
        # Test case 1: Call name exists in sourced module
        call_name = "func"
        expected_source_code = inspect.getsource(sourced_module.func)
        self.assertEqual(
            _trace_call(call_name, sourced_module),
            expected_source_code
        )
        
        # Test case 2: Call name does not exist in sourced module
        call_name = "nonexistent_func"
        self.assertIsNone(_trace_call(call_name, sourced_module))
        
        # Test case 3: Call name is nested in submodules
        setattr(sourced_module, "submodule1", ModuleType("submodule1"))
        setattr(
            sourced_module.submodule1, "submodule2", ModuleType("submodule2")
        )
        setattr(sourced_module.submodule1.submodule2, "func", lambda x: x + 1)
        
        call_name = "submodule1.submodule2.func"
        expected_source_code = inspect.getsource(
            sourced_module.submodule1.submodule2.func
        )
        self.assertEqual(
            _trace_call(call_name, sourced_module),
            expected_source_code
        )

class TestGetFunctionName(unittest.TestCase):
    
    def test_get_function_name_name(self):
        node = ast.Name(id='function_name', ctx=ast.Load())
        self.assertEqual(_get_function_name(node), 'function_name')
    
    def test_get_function_name_attribute(self):
        node = ast.Attribute(
            value=ast.Name(id='module', ctx=ast.Load()),
            attr='function_name',
            ctx=ast.Load()
        )
        self.assertEqual(_get_function_name(node), 'module.function_name')
    
    def test_get_function_name_call(self):
        node = ast.Call(
            func=ast.Name(id='function_name', ctx=ast.Load()),
            args=[],
            keywords=[]
        )
        self.assertEqual(_get_function_name(node), 'function_name')
    
    def test_get_function_name_constant(self):
        node = ast.Constant(value='function_name')
        self.assertEqual(_get_function_name(node), 'function_name')
    
    def test_get_function_name_subscript(self):
        node = ast.Subscript(
            value=ast.Name(id='list', ctx=ast.Load()),
            slice=ast.Index(value=ast.Constant(value=0)),
            ctx=ast.Load()
        )
        self.assertEqual(_get_function_name(node), 'list')
