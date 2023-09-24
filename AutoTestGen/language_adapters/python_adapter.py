from .base_adapter import BaseAdapter
import ast
import os
import sys
import inspect
import importlib
import pkgutil
from typing import Union
import tempfile
import unittest
import coverage
import traceback

# Import Visitor
class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        # modules is a dict of asname:module pair
        self.modules = dict()
        self.import_string = ''

    def visit_Import(self, node):
        self.import_string += f"\n{ast.unparse(node)}"
        for alias in node.names:
            if alias.asname:
                self.modules[alias.asname] = alias.name
            else:
                self.modules[alias.name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module
        if module:
            self.import_string += f"\n{ast.unparse(node)}" 
            for alias in node.names:
                if alias.asname:
                    self.modules[alias.asname] = module
                else:
                    self.modules[alias.name] = module
        else:
            self.visit_Import(node)
        self.generic_visit(node)

# Call visitor
class CallVisitor(ast.NodeVisitor):
    def __init__(self, sourced_module):
        self.sourced_module = sourced_module
        self.func_names = set()
        self.instances = {}
    def get_function_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self.get_function_name(node.value) + '.' + node.attr
    
    def visit_Call(self, node):
        fun_name = self.get_function_name(node.func)
        if fun_name:
            self.func_names.add(fun_name)                
        self.generic_visit(node)
    
    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Tuple):
                for target_name, value in zip(target.dims, node.value.dims):
                    if isinstance(value, ast.Call):
                        func_name = self.get_function_name(value.func)
                        if self._check_func_name(func_name, self.sourced_module):
                            self.instances[target_name.id] = func_name
            
            elif isinstance(target, ast.Name):
                if isinstance(node.value, ast.Call):
                    func_name = self.get_function_name(node.value.func)
                    if self._check_func_name(func_name, self.sourced_module):
                        self.instances[target.id] = func_name
    
    def visit_AnnAssign(self, node):
        if isinstance(node.value, ast.Call):
            func_name = self.get_function_name(node.value.func)
            if self._check_func_name(func_name, self.sourced_module):
                self.instances[node.traget.id] = func_name
        if node.value is None:
            # Case of annotations
            if isinstance(node.annotation, ast.Name):
                class_name = self.get_function_name(node.annotation)
            if isinstance(node.annotation, ast.Subscript):
                class_name = self.get_function_name(node.annotation.slice)
            if self._check_func_name(class_name, self.sourced_module):
                self.instances[node.target.id] = class_name
    
    def _check_func_name(self, func_name, sourced_module):
        submodules = func_name.split('.')
        if func_name in dir(sourced_module) or submodules[0] in dir(sourced_module):
            if len(submodules) != 1:
                func_name = submodules[-1]
                for submodule in submodules[:-1]:
                    sourced_module = getattr(sourced_module, submodule)
            if inspect.isclass(getattr(sourced_module, func_name)):
                return True
        return False


class PythonAdapter(BaseAdapter):
    def __init__(self, module: str, library: str=None, testing_framework: str="unittest"):
        super().__init__(language="python", testing_framework=testing_framework)
        self.suffix = ".py"
        self.library = library
        self.module = module
        if library is not None:
            self.library_imported = importlib.import_module(library)
            if not hasattr(self.library_imported, '__path__'):
                raise ValueError(f"{library} should be an installed package. Install the package locally first.")
        else:
            self.library_imported = None

        # Start-up
        self.sourced_module = self._source_module(module)
        self.source_code = self._get_module_code(module)
        self.syntax_tree = self._build_ast(self.source_code)
        self.modules_local, self.modules_all = self._get_local_modules(self.syntax_tree)
        
        # primitives for identifying constants
        self.primitives = (str, int, float, complex, list, tuple,
                      range, dict, set, frozenset, bool, bytes, bytearray, memoryview, type(None))
        
        # Body
        self.imports_string = self._get_imports_string(self.syntax_tree)
        self.imported_constants_str = self._get_imported_constants(self.modules_all)
        self.body_class_nodes = self._get_body_class_nodes(self.syntax_tree)
        self.body_func_nodes = self._get_body_func_nodes(self.syntax_tree)
        self.body_funcs = [node.name for node in self.body_func_nodes]
        self.body_classes = [node.name for node in self.body_class_nodes]
        self.constants_string = self._get_body_constants_str(self.syntax_tree)
        self.body_instances = self._get_body_instances(self.syntax_tree)

    def retrieve_func_defs(self):
        """Returns list of function names avaliable for testing"""
        return self.body_funcs

    def retrieve_class_defs(self):
        """Returns list of class names avaliable for testing"""
        return self.body_classes
    
    def prepare_prompt(self, obj_name: str, method_name: str=None):
        """
        Prepare prompts (list of messages) for the API.

        Parameters:
            obj_name (list): Name of an object (class- or function- definition) to test.

        Returns:
            list: containing messages for API.

        Raises:
            ValueError: If the provided obj_name or method_name cannot be found in given module or script.
        """
        
        if obj_name not in self.body_funcs + self.body_classes:
            raise ValueError(f"There is no class or function definition called: {obj_name} in the {self.module}")
        elif obj_name in self.body_funcs:
            messages = self._prepare_prompt_func(obj_name)
        elif obj_name in self.body_classes:
            messages = self._prepare_prompt_class(obj_name, method_name)
        return messages
    
    def run_tests_with_coverage(self, test_source):
        """
        Takes ChatGPT generated string code for tests runs them while tracking coverage.

        Parameters:
            test_source (str): Response string returned by the OpenAI API.

        Returns:
            (Coverage.control.Coverage) instance for coverage results.
            (unittest.runner.TextTestResult) instance for test results.
            
        Exception:
            If their is a problem compiling the code provided by ChatGPT, exception message string is returned for reprompting purposes.
        """

        # Before We start tracking coverage we unload the module so the definiton lines are tracked correctly
        if self.library:
            del(sys.modules[self.library + "." + self.module[:-3]])
        else:
            del(sys.modules[self.module[:-3]])
        
        # Start Recording Coverage
        cov = coverage.Coverage(source=["module1"], messages=True)
        cov.start()
        # Setup Temporary file for Test code
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=self.suffix) as temp_file:
            temp_file.write(test_source)
            temp_fn = temp_file.name
        # Setup file for coverage report
        cov_report = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json")
        
        try:
            # Try Loading Temp file as module: Checks if provided code by ChatGPT is a valid module/script
            spec = importlib.util.spec_from_file_location(os.path.basename(temp_fn)[:-3], temp_fn)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        
        except Exception as e:
            return None, traceback.format_exception_only(type(e), e)
        
        finally:
            # Close and delete temp files
            temp_file.close(), cov_report.close()
            os.remove(temp_fn), os.remove(cov_report.name)
        
        # Set-up Tests
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(module=module)
        runner = unittest.TextTestRunner(verbosity=2, warnings=False)
        # Run Tests
        result = runner.run(test_suite)
        cov.stop()
        cov.save()
        return result, cov

    def _prepare_prompt_func(self, name: str):
        """Helper Function for 'prepare_prompt' to generate Prompts for testing a Function definition."""
        n = 0
        node = self.body_func_nodes[self.body_funcs.index(name)]
        # System
        system_content = f'Generate high-quality comprehensive Unit-Tests in {self.language} '\
            f'using {self.framework} library for provided Function Definiton. '\
            f'Next to the Function Definiton you will be provided with numbered INFO Sheet that might be useful in generating finer Unit-Tests. '\
            f'You do not necessarily have to use all the information from the INFO sheet, but only the relevant parts. '\
            f'Your renspose should be just {self.language} code without explanation.'
        
        # INFO Sheet
        user_content = f'Function Definition:\n{ast.unparse(node)}\n\nINFO Sheet:'
        
        # INFO Sheet: location
        n += 1
        user_content = f'{user_content}\n{n}. '\
            f"Function is defined in '{self.module[:-3]}' module"
        if self.library:
            user_content = user_content + f' of {self.library} package'

        # INFO Sheet: Imports
        if self.imports_string != '':
            n += 1
            user_content = f'{user_content}\n{n}. '\
                f'Following imports were made to the namespace:{self.imports_string}'
        
        # INFO Sheet: Imported Constants
        if self.imported_constants_str != '':
            n += 1
            user_content = f'{user_content}\n{n}. '\
                f'Following Constants were imported to the namespace:{self.imported_constants_str}'

        # INFO Sheet: Variables
        if self.constants_string != '':
            n += 1
            user_content = f'{user_content}\n{n}. '\
                f'Following Variables were decleared in the namespace:{self.constants_string}'

        # INFO Sheet: Definitions of calls of functions and methods defined locally
        local_calls = self._get_relevant_calls(node)
        if not len(local_calls):
            for call in local_calls:
                n += 1
                if self._is_method(call, self.sourced_module):
                    user_content = f'{user_content}\n{n}. '\
                        f'Method Definition for {call}:\n{self._trace_call(call, self.sourced_module)}'
                    if self._has_init(call, self.sourced_module):
                        user_content = f"{user_content}\n'Associated class __init__ definition:\n{self._get_init(call, self.sourced_module)}"
                else:
                    user_content = f'{user_content}\n{n}. '\
                        f'Definiton for {call}:\n{self._trace_call(call, self.sourced_module)}'
        messages = [
            {'role': 'system', 'content': system_content},
            {'role': 'user', 'content': user_content}
        ]
        return messages

    def _prepare_prompt_class(self, name: str, method_name):
        """Helper Function for 'prepare_prompt' to generate Prompts for testing a Class definition."""
        n = 0
        # Selected class node
        class_node = self.body_class_nodes[self.body_classes.index(name)]
        method_nodes = self._get_body_func_nodes(class_node)
        method_names = [method.name for method in method_nodes]
        attributes_str = self._get_body_constants_str(class_node)

        if method_name is not None:
                if method_name not in method_names:
                    raise ValueError(f"There is no method called: {method_name} in class definiton for: {class_node.name}")
                else:
                    method_selected = [method_nodes[method_names.index(method_name)]]
        else:
            method_selected = method_nodes.copy()

        for node in method_selected:
            n = 0
            print(f"Starting generating Tests for method: {node.name}")

            # System
            system_content = f'Generate high-quality comprehensive Unit-Tests in {self.language} '\
                f'using {self.framework} library for provided Classmethod Definiton of a class called: {class_node.name}. '\
                f'Next to the Classmethod Definiton you will be provided with numbered INFO Sheet that might be useful in generating finer Unit-Tests. '\
                f'You do not necessarily have to use all the information from the INFO sheet, but only the relevant parts. '\
                f'Your renspose should be just {self.language} code without explanation.'

            # INFO Sheet:
            user_content = f'Classmethod Definition:\n{ast.unparse(node)}\n\nINFO Sheet:'
            
            # INFO Sheet: Location
            n += 1
            user_content = f'{user_content}\n{n}. '\
                f"Class is defined in '{self.module[:-3]}' module"
            if self.library:
                user_content = user_content + f" of '{self.library}' package"

            # INFO Sheet: __init__ if avaliable
            if '__init__' in method_names and node.name != '__init__':
                n += 1
                user_content = f'{user_content}\n{n}. '\
                    f"Definition of Class __init__:\n{ast.unparse(method_nodes[method_names.index('__init__')])}"
            
            # INFO Sheet: Class Attributes
            if attributes_str != '':
                n += 1
                user_content = f'{user_content}\n{n}. '\
                    f'Class contains following attributes:{attributes_str}'

            # INFO Sheet: Imports
            if self.imports_string != '':
                n += 1
                user_content = f'{user_content}\n{n}. '\
                    f'Following imports were made to the namespace:{self.imports_string}'
            
            # INFO Sheet: Imported Constants
            if self.imported_constants_str != '':
                n += 1
                user_content = f'{user_content}\n{n}. '\
                    f'Following Constants were imported to the namespace:{self.imported_constants_str}'

            # INFO Sheet: Variables        
            if self.constants_string != '':
                n += 1
                user_content = f'{user_content}\n{n}. '\
                    f'Following Variables were decleared in the namespace:{self.constants_string}'
            
            # INFO Sheet: Definitions of calls of functions and methods defined locally
            local_calls = self._get_relevant_calls(node, method=True, class_name=node.name)
            if not len(local_calls):
                for call in local_calls:
                    n += 1
                    if self._is_method(call, self.sourced_module):
                        user_content = f'{user_content}\n{n}. '\
                            f'Method Definition for {call}:\n{self._trace_call(call, self.sourced_module)}'
                        if self._has_init(call, self.sourced_module, omit=class_node.name):
                            user_content = f"{user_content}\n'Associated class __init__ definition:\n{self._get_init(call, self.sourced_module)}"
                    else:
                        user_content = f'{user_content}\n{n}. '\
                            f'Definiton for {call}:\n{self._trace_call(call, self.sourced_module)}'

        messages = [
            {'role': 'system', 'content': system_content},
            {'role': 'user', 'content': user_content}
        ]
        return messages

    def _source_module(self, module:str):
        if not module.endswith(self.suffix):
            raise Exception(f"Module should be a python module with a {self.suffix} extension")
        if self.library_imported is None:
            sourced_module = importlib.import_module(module[:-3])
        else:
            sourced_module = getattr(self.library_imported, module[:-3])
        return sourced_module
        
    def _get_module_code(self, module:str):
        if self.library_imported is None:
            with open(module, "r") as file:
                source_code = file.read()
        else:
            source_code = inspect.getsource(getattr(self.library_imported, module[:-3]))
        return source_code

    def _build_ast(self, source_code:str):
        return ast.parse(source_code)
    
    def _get_local_modules(self, module_ast: ast.Module):
        # Identifies local modules, returns list of strings (module asnames)
        import_visitor = ImportVisitor()
        import_visitor.visit(module_ast)
        # Extract module names
        imported_mods = [*import_visitor.modules.values()]
        modules_all= [*import_visitor.modules.keys()]
        modules_local = set()
        if self.library_imported is not None:
            submodules = [submod.name for submod in [*pkgutil.iter_modules(self.library_imported.__path__)]]
        else:
            dir_path = os.path.dirname(os.path.join(os.getcwd(), self.module))
        
        for mod in imported_mods:
            # Package case
            if self.library_imported is not None:
                check = mod.startswith(".") or mod.startswith(f"{self.library}.") or mod == {self.library} or mod in submodules
            else:
            # Just module case
                local_files = [fn[:-3] for fn in os.listdir(dir_path) if fn.endswith(self.suffix)]
                local_files.extend([fn for fn in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, fn))])
                check = mod in local_files
            if check:
                # Add asnames
                for i, v in enumerate(imported_mods):
                    if v == mod:
                        modules_local.add(modules_all[i])
        return modules_local, modules_all

    def _get_imports_string(self, module_ast: ast.Module):
        # Returns import statements together in one string
        import_visitor = ImportVisitor()
        import_visitor.visit(module_ast)
        imports_string = import_visitor.import_string
        return imports_string
    
    def _get_imported_constants(self, modules_all):
        imported_consts_str = ''
        for module in modules_all:
            if type(getattr(self.sourced_module, module)) in self.primitives:
                imported_consts_str += f'\n{module} = {getattr(self.sourced_module, module)}'
        return imported_consts_str
    

    def _get_body_func_nodes(self, node: Union[ast.Module, ast.ClassDef]):
        func_nodes = [subnode for subnode in node.body if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef))]
        return func_nodes

    def _get_body_class_nodes(self, node: Union[ast.Module, ast.ClassDef]):
        class_nodes = [subnode for subnode in node.body if isinstance(subnode, ast.ClassDef)]
        return class_nodes

    def _get_body_constants_str(self, node: Union[ast.Module, ast.ClassDef]):
        constants_string = ''
        decleared_types = ''
        rest_nodes = [subnode 
                        for subnode in node.body 
                        if not isinstance(subnode, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))]
        for rest_node in rest_nodes:
            constants_string += f'\n{ast.unparse(rest_node)}'
            for subnode in ast.walk(rest_node):
                if isinstance(subnode, ast.Assign):
                    if isinstance(subnode.value, ast.Call):
                        call_name = self._get_function_name(subnode.value.func)
                        if call_name in self.body_funcs + self.body_classes or call_name in self.modules_local:
                            for name in subnode.targets:
                                decleared_types += f'\n{name.id}: {type(getattr(self.sourced_module, name.id))}'
        if decleared_types != '':
            final_string = f'{constants_string}\n'\
                f'Additionally data types for decleared variables whose types are not obvious:{decleared_types}'
        else:
            final_string = constants_string
        return final_string

    def _get_body_instances(self, module_ast: ast.Module):
        # Called from ast.Module on body returns dict{instance:class}
        call_visitor = CallVisitor(self.sourced_module)
        for node in module_ast.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                call_visitor.visit(node)
        instances_filtered = {key: value 
                              for key, value in call_visitor.instances.items()
                              if value in self.body_classes or value.split(".")[0] in self.modules_local}
        return instances_filtered
    
    def _get_relevant_calls(self, node: ast.FunctionDef, method=False, class_name=None):
        # Returns relevant function calls in an enclosed enviornment
        call_visitor = CallVisitor(self.sourced_module)
        call_visitor.visit(node)
        call_names = list(call_visitor.func_names)
        # Enclosed env has priority over global
        instances = self.body_instances.copy()
        instances.update(call_visitor.instances)
        
        # Swap instance name with associated class name in calls
        for i, call in enumerate(call_names):
            splits = call.split('.')
            if len(splits) > 1:
                if splits[0] in [*instances.keys()]:
                    splits[0] = instances[splits[0]]
                    call_names[i] = "".join(splits)
                if method:
                    indicator = node.args.args[0].arg
                    if splits[0] == indicator:
                        splits[0] = class_name
                        call_names[i] = "".join(splits)
        
        local_classes = list(self.modules_local) + self.body_classes
        local_functions = self.body_funcs + list(self.modules_local)
        local_calls = [name for name in call_names if name in local_functions or name.split(".")[0] in local_classes]
        local_calls = set(local_calls)
        return local_calls

    def _get_function_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_function_name(node.value) + '.' + node.attr
        
    def _trace_call(self, call_name, sourced_module):
        submodules = call_name.split('.')
        for submodule in submodules:
            sourced_module = getattr(sourced_module, submodule)
        return inspect.getsource(sourced_module)
    
    def _has_init(self, call_name, sourced_module, omit=None):
        submodules = call_name.split('.')
        class_name = submodules[0]
        if omit is not None:
            if class_name == omit:
                return False
        return hasattr(getattr(sourced_module, class_name), '__init__')
    
    def _get_init(self, call_name, sourced_module):
        submodules = call_name.split('.')
        class_def = getattr(sourced_module, submodules[0])
        return inspect.getsource(getattr(class_def, '__init__'))

    def _is_method(self, call_name, sourced_module):
        submodules = call_name.split('.')
        for submodule in submodules:
            sourced_module = getattr(sourced_module, submodule)
        return inspect.ismethod(sourced_module)
    

        



        