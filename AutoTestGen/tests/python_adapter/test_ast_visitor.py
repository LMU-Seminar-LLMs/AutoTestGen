import unittest
from unittest.mock import MagicMock
import ast
from types import ModuleType
from AutoTestGen.language_adapters.python_adapter import (
    AstVisitor,
    _get_function_name,
    _is_class
)

class TestImportVisitor(unittest.TestCase):
    def setUp(self):
        self.sourced_module = ModuleType("test_module")
        self.visitor = AstVisitor(self.sourced_module)

    def test_visit_Import_simple_import(self):
        node = ast.Import(names=[ast.alias(name="module1", asname=None)])
        self.visitor.visit_Import(node)
        self.assertEqual(self.visitor.import_statements, ["import module1"])
        self.assertEqual(self.visitor.modules, {"module1": "module1"})

    def test_visit_Import_alias_import(self):
        node = ast.Import(names=[ast.alias(name="module2", asname="mod2")])
        self.visitor.visit_Import(node)
        self.assertEqual(
            self.visitor.import_statements,
            ["import module2 as mod2"]
        )
        self.assertEqual(self.visitor.modules, {"mod2": "module2"})

    def test_visit_Import_multiple_imports(self):
        node = ast.Import(names=[
            ast.alias(name="module3", asname=None),
            ast.alias(name="module4", asname="mod4")
        ])
        self.visitor.visit_Import(node)
        self.assertEqual(
            self.visitor.import_statements,
            ["import module3, module4 as mod4"]
        )
        self.assertEqual(
            self.visitor.modules,
            {"module3": "module3", "mod4": "module4"}
        )

    def test_visit_Import_empty_import(self):
        node = ast.Import(names=[])
        self.visitor.visit_Import(node)
        self.assertEqual(self.visitor.import_statements, [])
        self.assertEqual(self.visitor.modules, {})

    def test_visit_Import_with_existing_imports(self):
        self.visitor.import_statements = ["import module5"]
        self.visitor.modules = {"mod5": "module5"}

        node = ast.Import(names=[ast.alias(name="module6", asname=None)])
        self.visitor.visit_Import(node)
        self.assertEqual(
            self.visitor.import_statements,
            ["import module5", "import module6"]
        )
        self.assertEqual(
            self.visitor.modules,
            {"mod5": "module5", "module6": "module6"}
        )

class TestImportFromVisitor(unittest.TestCase):
    def setUp(self):
        self.module = ModuleType("test_module")
        self.ast_visitor = AstVisitor(self.module)

    def test_visit_ImportFrom(self):
        node = ast.parse("from math import sqrt")
        self.ast_visitor.visit_ImportFrom(node.body[0])
        self.assertEqual(
            self.ast_visitor.import_statements,
            ["from math import sqrt"]
        )
        self.assertEqual(self.ast_visitor.modules, {"sqrt": "math"})

    def test_visit_ImportFrom_with_alias(self):
        node = ast.parse("from math import sqrt as square_root")
        self.ast_visitor.visit_ImportFrom(node.body[0])
        self.assertEqual(
            self.ast_visitor.import_statements,
            ["from math import sqrt as square_root"]
        )
        self.assertEqual(self.ast_visitor.modules, {"square_root": "math"})

    def test_visit_ImportFrom_with_asterisk(self):
        node = ast.parse("from math import *")
        self.ast_visitor.visit_ImportFrom(node.body[0])
        self.assertIn("sqrt", self.ast_visitor.modules)
        self.assertEqual(self.ast_visitor.modules["sqrt"], "math")

    def test_visit_ImportFrom_relative_import(self):
        node = ast.parse("from . import sqrt")
        self.ast_visitor.visit_ImportFrom(node.body[0])
        self.assertEqual(
            self.ast_visitor.import_statements,
            ["from . import sqrt"]
        )
        self.assertEqual(self.ast_visitor.modules, {"sqrt": "sqrt"})

    def test_visit_ImportFrom_no_module(self):
        node = ast.parse("from . import sqrt")
        setattr(node.body[0], "module", None)
        self.ast_visitor.visit_ImportFrom(node.body[0])
        self.assertEqual(
            self.ast_visitor.import_statements,
            ["from . import sqrt"]
        )
        self.assertEqual(self.ast_visitor.modules, {"sqrt": "sqrt"})

class TestCallVisitor(unittest.TestCase):
    def setUp(self):
        self.visitor = AstVisitor(ModuleType)

    def test_visit_Call_with_fun_name(self):
        node = ast.Call(
            func=ast.Name(id='function_name',ctx=ast.Load()),
            args=[],
            keywords=[]
        )
        self.visitor.visit_Call(node)
        self.assertIn('function_name', self.visitor.func_names)

    def test_visit_Call_without_fun_name(self):
        node = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='module_name', ctx=ast.Load()),
                attr='function_name',
                ctx=ast.Load()
            ),
            args=[],
            keywords=[]
        )
        self.visitor.visit_Call(node)
        self.assertNotIn('function_name', self.visitor.func_names)

    def test_visit_Call_with_nested_Call(self):
        nested_node = ast.Call(
            func=ast.Name(id='nested_function', ctx=ast.Load()),
            args=[],
            keywords=[]
        )
        node = ast.Call(
            func=ast.Name(id='function_name', ctx=ast.Load()),
            args=[nested_node], keywords=[]
        )
        self.visitor.visit_Call(node)
        self.assertIn('function_name', self.visitor.func_names)
        self.assertIn('nested_function', self.visitor.func_names)

    def test_visit_Call_with_multiple_calls(self):
        node1 = ast.Call(
            func=ast.Name(id='function1', ctx=ast.Load()),
            args=[],
            keywords=[]
        )
        node2 = ast.Call(
            func=ast.Name(id='function2', ctx=ast.Load()),
            args=[],
            keywords=[]
        )
        node = ast.Call(
            func=ast.Name(id='function_name', ctx=ast.Load()),
            args=[node1, node2],
            keywords=[]
        )
        self.visitor.visit_Call(node)
        self.assertIn('function_name', self.visitor.func_names)
        self.assertIn('function1', self.visitor.func_names)
        self.assertIn('function2', self.visitor.func_names)

    def test_generic_visit_with_list_of_nodes(self):
        node1 = ast.Call(
            func=ast.Name(id='function1', ctx=ast.Load()),
            args=[],
            keywords=[]
        )
        node2 = ast.Call(
            func=ast.Name(id='function2', ctx=ast.Load()),
            args=[],
            keywords=[]
        )
        node = ast.Module(body=[node1, node2])
        self.visitor.generic_visit(node)
        self.assertIn('function1', self.visitor.func_names)
        self.assertIn('function2', self.visitor.func_names)

class TestAssignVisitor(unittest.TestCase):
    def setUp(self):
        self.sourced_module = ModuleType("sourced_module")
        class ClassName: pass
        class ClassName2: pass
        setattr(self.sourced_module, "ClassName", ClassName)
        setattr(self.sourced_module, "ClassName2", ClassName2)
        self.visitor = AstVisitor(self.sourced_module)

    def test_visit_Assign_single_target_call_assignment_class_instance(self):
        node = ast.Assign(
            targets=[ast.Name(id="target")],
            value=ast.Call(func=ast.Name(id="ClassName"))
        )
        self.visitor.visit_Assign(node)
        self.assertEqual(self.visitor.instances.get("target"), "ClassName")

    def test_visit_Assign_single_target_call_assignment_not_class_instance(self):
        node = ast.Assign(
            targets=[ast.Name(id="target")],
            value=ast.Call(func=ast.Name(id="function"))
        )
        self.visitor.visit_Assign(node)
        self.assertEqual(self.visitor.func_names, {"function"})

    def test_visit_Assign_tuple_assignment_single_value_class_instance(self):
        node = ast.Assign(
            targets=[ast.Tuple(elts=[ast.Name(id="target")])],
            value=ast.Call(func=ast.Name(id="ClassName"))
        )
        self.visitor.visit_Assign(node)
        self.assertEqual(self.visitor.instances.get("target"), "ClassName")

    def test_visit_Assign_tuple_assignment_single_value_not_class_instance(self):
        node = ast.Assign(
            targets=[ast.Tuple(elts=[ast.Name(id="target")])],
            value=ast.Call(func=ast.Name(id="function"))
        )
        self.visitor.visit_Assign(node)
        self.assertEqual(self.visitor.func_names, {"function"})

    def test_visit_Assign_tuple_assignment_multiple_values_class_instance(self):
        node = ast.Assign(
            targets=[
                ast.Tuple(
                    elts=[
                        ast.Name(id="target1"),
                        ast.Name(id="target2")
                    ]
                )
            ],
            value=ast.Tuple(
                elts=[
                    ast.Call(func=ast.Name(id="ClassName")),
                    ast.Call(func=ast.Name(id="ClassName2"))
                ]
            )
        )
        self.visitor.visit_Assign(node)
        self.assertEqual(self.visitor.instances.get("target1"), "ClassName")
        self.assertEqual(self.visitor.instances.get("target2"), "ClassName2")

    def test_visit_Assign_tuple_assignment_multiple_values_not_class_instance(self):
        node = ast.Assign(
            targets=[
                ast.Tuple(
                    elts=[
                        ast.Name(id="target1"),
                        ast.Name(id="target2")
                    ]
                )
            ],
            value=ast.Tuple(
                elts=[
                    ast.Call(func=ast.Name(id="function1")),
                    ast.Call(func=ast.Name(id="function2"))
                ]
            )
        )
        self.visitor.visit_Assign(node)
        self.assertEqual(self.visitor.func_names, {"function1", "function2"})

    def test_AnnAssign_class_instance(self):
        node = ast.AnnAssign(
            target=ast.Name(id="target"),
            annotation=ast.Name(id="ClassName"),
            value=ast.Call(
                func=ast.Name(id='ClassName', ctx=ast.Load()),
                args=[ast.Constant(value='Hello World!')],
                keywords=[]
            ),
            simple=1
        )
        self.visitor.visit_AnnAssign(node)
        self.assertEqual(self.visitor.instances.get("target"), "ClassName")

    def test_AnnAssign_without_value(self):
        node = ast.AnnAssign(
            target=ast.Name(id="target"),
            annotation=ast.Name(id="ClassName"),
            value=None,
            simple=1
        )
        self.visitor.visit_AnnAssign(node)
        self.assertEqual(self.visitor.instances.get("target"), "ClassName")

class TestRestoreVisitor(unittest.TestCase):

    def setUp(self):
        self.sourced_module = MagicMock()
        self.visitor = AstVisitor(self.sourced_module)

    def test_restore_visitor(self):
        self.visitor.import_statements = ['import os', 'import sys']
        self.visitor.modules = {
            'module1': 'path/to/module1',
            'module2': 'path/to/module2'
        }
        self.visitor.func_names = {'func1', 'func2'}
        self.visitor.instances = {
            'instance1': 'path/to/instance1',
            'instance2': 'path/to/instance2'
        }

        self.visitor.restore_visitor()
        self.assertEqual(self.visitor.import_statements, [])
        self.assertEqual(self.visitor.modules, {})
        self.assertEqual(self.visitor.func_names, set())
        self.assertEqual(self.visitor.instances, {})











