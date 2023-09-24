from .base_adapter import BaseAdapter
import ast
import os
import json
import sys
import inspect
import importlib, importlib.util
from typing import Union
from types import ModuleType
import tempfile
import unittest
import coverage
import traceback
from ..templates import INITIAL_SYSTEM_PROMPT, INITIAL_USER_PROMPT, generate_python_info_sheet


class AstVisitor(ast.NodeVisitor):
    def __init__(self, sourced_module: ModuleType):
        self.sourced_module = sourced_module
        self.imports_string : str = ''
        self.modules : dict[str, str] = dict()
        self.func_names : set = set()
        self.instances : dict = dict()


    def visit_Import(self, node) -> None:
        self.imports_string += f"\n{ast.unparse(node)}"
        for alias in node.names:
            if alias.asname:
                # Alias import
                self.modules[alias.asname] = alias.name
            else:
                # Simple import
                self.modules[alias.name] = alias.name
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node) -> None:
        module = node.module
        if module:
            self.imports_string += f"\n{ast.unparse(node)}"
            for alias in node.names:
                # From import with alias
                if alias.asname:
                    self.modules[alias.asname] = module
                else:
                    # Simple from import
                    if alias.name != '*':
                        self.modules[alias.name] = module
                    else:
                        # dynamically import module
                        module_asterisked = importlib.import_module(module)
                        # add all names to the namespace except imported modules inside that module
                        module_asterisked_imports = inspect.getmembers(module_asterisked, inspect.ismodule)
                        module_asterisked_import_names = [name for name, _ in module_asterisked_imports]
                        self.modules.update(
                            {name: module
                             for name in dir(module_asterisked)
                             if not name.startswith('__') and name not in module_asterisked_import_names}
                        ) 
        else:
            self.visit_Import(node)
        self.generic_visit(node)

    def visit_Call(self, node) -> None:
        """Collects function names from Call nodes"""
        fun_name = self._get_function_name(node.func)
        if fun_name:
            self.func_names.add(fun_name)                
        self.generic_visit(node)
    
    def visit_Assign(self, node) -> None:
        """Searches for class instance creations and collects them to track their methods later"""
        for target in node.targets:
            # Simple single target:call assignment
            if isinstance(target, ast.Name):
                if isinstance(node.value, ast.Call):
                    func_name = self._get_function_name(node.value.func)
                    if self._is_class(func_name, self.sourced_module):
                        self.instances[target.id] = func_name 
            elif isinstance(target, ast.Tuple):
                # Tuple assignment with multiple targets
                for target_name, value in zip(target.dims, node.value.dims):
                    if isinstance(value, ast.Call):
                        func_name = self._get_function_name(value.func)
                        if self._is_class(func_name, self.sourced_module):
                            self.instances[target_name.id] = func_name
    
    def visit_AnnAssign(self, node):
        """
        Searches for class instance creations and collects them to track their methods later.
        Serves for the special case of annotated assignments.
        """
        if isinstance(node.value, ast.Call):
            # simple annotated assignment
            func_name = self._get_function_name(node.value.func)
            if self._is_class(func_name, self.sourced_module):
                self.instances[node.traget.id] = func_name
        
        if node.value is None:
            # Hint annotation without actual value assignment
            if isinstance(node.annotation, ast.Name):
                class_name = self._get_function_name(node.annotation)
            if isinstance(node.annotation, ast.Subscript):
                class_name = self._get_function_name(node.annotation.slice)
            if self._is_class(class_name, self.sourced_module):
                self.instances[node.target.id] = class_name

    def _is_class(self, func_name, sourced_module) -> bool:
        """Helper function for Assign visitors. Checks if a function call is a class [instance creation]"""
        submodules = func_name.split('.')
        if func_name in dir(sourced_module) or submodules[0] in dir(sourced_module):
            if len(submodules) != 1:
                func_name = submodules[-1]
                for submodule in submodules[:-1]:
                    sourced_module = getattr(sourced_module, submodule)
                if sourced_module is not None:
                    return inspect.isclass(getattr(sourced_module, func_name))
        return False

    def _get_function_name(self, node) -> str:
        """Helper function for visit_Call. Returns function name from a Call node through recursion"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_function_name(node.value) + '.' + node.attr
        elif isinstance(node, ast.Call):
            return self._get_function_name(node.func)
        elif isinstance(node, ast.Constant):
            return node.value


class PromptPreparer:
    def __init__(self, sourced_module: ModuleType):
        # Start-up
        self.sourced_module = sourced_module
        self.source_code = inspect.getsource(sourced_module)
        self.syntax_tree = ast.parse(self.source_code)

        # Body Class Nodes
        self.body_class_nodes = [subn for subn in self.syntax_tree.body if isinstance(subn, ast.ClassDef)]
        self.body_class_names = [node.name for node in self.body_class_nodes]
        # Body Func Nodes
        self.body_func_nodes = [subn for subn in self.syntax_tree.body if isinstance(subn, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.body_func_names = [node.name for node in self.body_func_nodes]

        self.ast_visitor = AstVisitor(self.sourced_module)
        # Run the visitor on the syntax tree except the FunctionDef, ClassDef and AsyncFunctionDef nodes
        for node in self.syntax_tree.body:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self.ast_visitor.visit(node)
        
        # 1. Imports string
        self.imports_string = self.ast_visitor.imports_string
        self.modules_all = [*self.ast_visitor.modules.keys()]
        self.modules_local = self.get_local_modules(self.modules_all)
        
        # 2. Imported constants string
        # primitives for identifying constants
        self.primitives = (str, int, float, complex, list, tuple,
                      range, dict, set, frozenset, bool, bytes, bytearray, memoryview, type(None))
        self.imported_constants_str = self.get_imported_constants_str(self.modules_all)
        
        # 3. Body variable assignments
        self.variables_string = self.get_body_variables_str(self.syntax_tree)

        # 4. Identify body Instances
        self.body_instances = {
            k:v for k, v in self.ast_visitor.instances.items()
            if v in self.body_class_names or v.split(".")[0] in self.modules_local
        }
        
    def get_body_variables_str(self, node: Union[ast.Module, ast.ClassDef]):
        """Handels all the rest body nodes except imports, classes and functions"""
        variables_string = ''
        decleared_types = ''
        rest_nodes = [
            subn 
            for subn in node.body 
            if not isinstance(subn, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
        ]
        
        for rest_node in rest_nodes:
            variables_string += f'\n{ast.unparse(rest_node)}'
            # Body Level assignments
            if isinstance(rest_node, ast.Assign):
                if isinstance(rest_node.value, ast.Call):
                    call_name = self.ast_visitor._get_function_name(rest_node.value.func)
                    if call_name in self.body_func_names + self.body_class_names or call_name in self.modules_local:
                        for name in rest_node.targets:
                            decleared_types += f'\n{name.id}: {type(getattr(self.sourced_module, name.id))}'
        if decleared_types != '':
            final_string = f'{variables_string}\n'\
                f'Additionally data types for body-decleared variables whose types are not obvious:{decleared_types}'
        else:
            final_string = variables_string
        return final_string

    def get_local_modules(self, modules_all: list) -> list:
        """Returns list of local modules"""
        # Imported modules: actual module names
        imported_mods = [*self.ast_visitor.modules.values()]
        dir_path = os.path.dirname(self.sourced_module.__file__)
        # Collect local py files and dirs
        local_files = [fn for fn in os.listdir(dir_path) 
                       if os.path.isdir(os.path.join(dir_path, fn)) or fn.endswith(".py")]
        # Check if imported modules are local
        modules_local = []
        for mod in imported_mods:
            if mod.startswith(".") or mod.split(".")[0] in local_files:
                for i, v in enumerate(imported_mods):
                    if v == mod:
                        # Collect modules with asnames
                        modules_local.append(modules_all[i])
        return modules_local
    
    def get_imported_constants_str(self, modules_all: list) -> str:
        imported_consts_str = ''
        for module in modules_all:
            traced_module = self._trace_module(module, self.sourced_module)
            if type(getattr(traced_module, module.split(".")[-1])) in self.primitives:
                imported_consts_str += f'\n{module} = {getattr(traced_module, module.split(".")[-1])}'
        return imported_consts_str
    
    def retrieve_func_node(self, obj_name, method=None):
        """Returns function node given a function name"""
        if method is None:
            node = self.body_func_nodes[self.body_func_names.index(obj_name)]
        else:
            class_node = self.retrieve_class_node(obj_name)
            method_nodes = [
                subn
                for subn in class_node.body 
                if isinstance(subn, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            method_names = [method.name for method in method_nodes]
            node = method_nodes[method_names.index(method)]
        return node

    def retrieve_class_node(self, obj_name):
        """Returns class node given a class name"""
        return self.body_class_nodes[self.body_class_names.index(obj_name)]

    def  get_local_calls(
            self,
            node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
            method=False,
            class_name=None
        ) -> set:
        # Restore the visitor
        self.ast_visitor.func_names = set()
        self.ast_visitor.instances = {}
        self.ast_visitor.visit(node)
        call_names: list[str] = list(self.ast_visitor.func_names)
        # Enclosed env has priority over global
        instances = self.body_instances.copy()
        instances.update(self.ast_visitor.instances)

        # Swap instance name with associated class name in calls
        for i, call in enumerate(call_names):
            splits = call.split('.')
            if len(splits) > 1:
                if splits[0] in [*instances.keys()]:
                    splits[0] = instances[splits[0]]
                if method:
                    indicator = node.args.args[0].arg
                    if splits[0] == indicator:
                        splits[0] = class_name
                call_names[i] = '.'.join(splits)
        local_classes = list(self.modules_local) + self.body_class_names
        local_functions = list(self.modules_local) + self.body_func_names
        local_calls = [
            nm for nm in call_names
            if nm in local_functions or nm.split(".")[0] in local_classes
        ]
        return set(local_calls)

    def get_local_defs_str(self, local_calls: set, omit: str=None):
        local_defs = ''
        for call in local_calls:
            if self._is_method(call, self.sourced_module):
                # If call is a class method call
                local_defs += f'\nMethod Definition for {call}:\n{self._trace_call(call, self.sourced_module)}'
                if self._has_init(call, self.sourced_module, omit=omit):
                    # If class has init provide additional info
                    local_defs += f"\n'Associated class __init__ definition:\n{self._get_init(call, self.sourced_module)}"
                else:
                    # If it is simple local function call
                    local_defs += f'\nDefiniton for {call}:\n{self._trace_call(call, self.sourced_module)}'
        return local_defs

    def _is_method(self, call_name, sourced_module) -> bool:
        """Helper Function checks if a call is a class method"""
        submodules = call_name.split('.')
        for submodule in submodules:
            try:
                sourced_module = getattr(sourced_module, submodule)
            except:
                return False
        return inspect.ismethod(sourced_module)
    
    def _has_init(self, call_name, sourced_module, omit=None) -> bool:
        """Helper Function checks if a class has an __init__ method"""
        submodules = call_name.split('.')
        class_name = submodules[0]
        if omit is not None:
            if class_name == omit:
                return False
        return inspect.isfunction(getattr(getattr(sourced_module, class_name), '__init__'))
    
    def _get_init(self, call_name, sourced_module):
        """Helper Function returns __init__ method definition of a class"""
        submodules = call_name.split('.')
        class_def = getattr(sourced_module, submodules[0])
        return inspect.getsource(getattr(class_def, '__init__'))

    def _trace_module(self, module_name, sourced_module) -> ModuleType:
        """Helper Function traces a module recursively until reaching the module itself"""
        submodules = module_name.split('.')
        for submodule in submodules[:-1]:
            sourced_module = getattr(sourced_module, submodule)
        return sourced_module
    
    def _trace_call(self, call_name, sourced_module) -> str:
        """Helper Function traces a call recursively until reaching the function itself"""
        submodules = call_name.split('.')
        for submodule in submodules:
            sourced_module = getattr(sourced_module, submodule)
        return inspect.getsource(sourced_module)


class PythonAdapter(BaseAdapter):
    suffix = ".py"
    def __init__(self, module: str, testing_framework: str="unittest"):
        super().__init__(language="python", testing_framework=testing_framework)
        
        # Id attributes
        self.module = module
        if module.startswith("/"): 
            self.mod_name = module[1:].replace('/', '.')[:-3]
        else:
            self.mod_name = module[:-3].replace('/', '.')
        print(self.mod_name)
        self.suffix = self.__class__.suffix

        # PromptPreparer
        self.sourced_module = self._source_module(module)
        self.prompt_preparer = PromptPreparer(self.sourced_module)


    def retrieve_func_defs(self):
        """Returns list of function names avaliable in module/script Body"""
        return self.prompt_preparer.body_func_names

    def retrieve_class_defs(self):
        """Returns list of class names avaliable in module/script Body"""
        return self.prompt_preparer.body_class_names
    
    def retrieve_class_methods(self, class_name: str):
        """Returns list of methods of a class given a class name"""
        class_node = self.prompt_preparer.body_class_nodes[self.prompt_preparer.body_class_names.index(class_name)]
        method_nodes = [subn for subn in class_node.body if isinstance(subn, (ast.FunctionDef, ast.AsyncFunctionDef))]
        method_names = [method.name for method in method_nodes]
        return method_names
    
    def retrieve_module_source(self) -> str:
        """Returns source code of a module"""
        return inspect.getsource(self.sourced_module)

    def retrieve_func_source(self, func_name: str) -> str:
        """Returns source code of a function definiton given a function name"""
        return inspect.getsource(getattr(self.sourced_module, func_name))
    
    def retrieve_class_source(self, class_name: str) -> str:
        """Returns source code of a class definition given a class name"""
        return inspect.getsource(getattr(self.sourced_module, class_name))
    
    def retrieve_classmethod_source(self, class_name: str, method_name: str) -> str:
        """Returns source code of a method definition given a class name and method name"""
        return inspect.getsource(getattr(getattr(self.sourced_module, class_name), method_name))

    def prepare_prompt(self, obj_name: str, method_name: str=None):
        if obj_name not in self.prompt_preparer.body_func_names + self.prompt_preparer.body_class_names:
            raise ValueError(f"There is no class or function definition called: {obj_name} in the {self.module}")
        
        # Two cases: Function or Class
        if obj_name in self.prompt_preparer.body_func_names and method_name is None:
            obj_type = "Function"
            obj_desc = "Function Definition"
            node = self.prompt_preparer.retrieve_func_node(obj_name)
            source_code = self.retrieve_func_source(obj_name)
            relevant_calls = self.prompt_preparer.get_local_calls(node)
            local_call_defs = self.prompt_preparer.get_local_defs_str(relevant_calls)

            info_sheet = generate_python_info_sheet(
                obj_type = obj_type,
                module_name=self.mod_name,
                imports=self.prompt_preparer.imports_string,
                constants=self.prompt_preparer.imported_constants_str,
                variables=self.prompt_preparer.variables_string,
                local_call_defs=local_call_defs
            )
        
        elif obj_name in self.prompt_preparer.body_class_names and method_name is not None:
            obj_type = "Class"
            obj_desc = f"Method Definition of a class called: {obj_name}"
            class_node = self.prompt_preparer.retrieve_class_node(obj_name)
            method_node = self.prompt_preparer.retrieve_func_node(obj_name, method_name)
            source_code = self.retrieve_classmethod_source(obj_name, method_name)
            
            if self.prompt_preparer._has_init(obj_name, self.sourced_module, omit=method_name):
                init = self.retrieve_classmethod_source(obj_name, "__init__")
            else:
                init = ''

            class_attributes = self.prompt_preparer.get_body_variables_str(class_node)
            relevant_calls = self.prompt_preparer.get_local_calls(method_node, method=True, class_name=obj_name)
            local_call_defs = self.prompt_preparer.get_local_defs_str(relevant_calls, omit=method_name)
            info_sheet = generate_python_info_sheet(
                obj_type = obj_type,
                module_name=self.mod_name,
                imports=self.prompt_preparer.imports_string,
                constants=self.prompt_preparer.imported_constants_str,
                variables=self.prompt_preparer.variables_string,
                local_call_defs=local_call_defs,
                class_name=obj_name,
                init=init,
                class_attributes=class_attributes
            )

        # Prepare system PROMPT
        additional_info =""
        # additional_info = "Make sure that the script is only executed from the __main__.\n" \
        #     f"Your response should start with: from {self.mod_name} import {obj_name}"
        
        system_prompt = INITIAL_SYSTEM_PROMPT.format(
            language=self.language,
            framework=self.framework,
            obj_desc= obj_desc,
            additional_info=additional_info
        )

        # Prepare system PROMPT
        user_prompt = INITIAL_USER_PROMPT.format(
            obj_type= "Function "if obj_type == "Function" else "Method",
            source_code=source_code,
            info_sheet=info_sheet
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        return messages
    
    def postprocess_response(self, test_source: str, **kwargs) -> str:
        """Adds import statement to the top of the test code in case it is missing"""
        print(f"Before postprocessing:\n{test_source}")
        obj_name = kwargs.get('obj_name')
        # Making sure that tested object is imported
        test_lines = test_source.split("\n")
        import_string = f"from {self.mod_name} import {obj_name}"
        import_asterisk = f"from {self.mod_name} import *"
        if not import_string in test_lines and not import_asterisk in test_lines:
            test_lines.insert(0, import_string)

        # Making sure script is only executed when ran from main
        if not "if __name__ == '__main__':" in test_lines:
            test_lines.append("if __name__ == '__main__':")
            test_lines.append("    unittest.main()")

        # GPT-4 very often wraps response in ```python``` code block and adds extra explanation lines even though explicilty asked not to
        if "```python" in test_lines:
            start_index = test_lines.index("```python")
            end_index = test_lines.index("```")
            test_lines = test_lines[start_index+1:end_index]
        return "\n".join(test_lines)

        


    
    def run_tests_with_coverage(self, test_source: str):
        """
        Takes a string of code generated by ChatGPT and runs it for testing while tracking code coverage.

        Parameters:
            test_source (str): The response string returned by the OpenAI API.

        Returns:
            dict: A dictionary containing specific key-value pairs.\n
                - 'tests_ran_n': The number of tests that ran (list[int]).\n
                - 'errors': A list of tuples containing (test_id, traceback_message)
                            for tests with errors (list[tuple(str, str)]).\n
                - 'failures': A list of tuples containing (test_id, traceback_message)
                            for tests with failures (list[tuple(str, str)]).\n
                - 'executed_lines': A list of executed line numbers [based on the entire module or script] (list[int]).\n
                - 'missing_lines': A list of missing line numbers [based on the entire module or script] (list[int]).

        Exception:
            If there is a problem compiling the code provided by ChatGPT,
            an exception message string is returned for reprompting purposes.
        """
        # Before We start tracking coverage we unload the module so the definiton lines are tracked correctly
        if self.mod_name in sys.modules:
            del sys.modules[self.mod_name]
        # Create Temp file for json report
        temp_json = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json")

        # Start Recording Coverage
        print("source:\n" + test_source)
        
        print("Starting Coverage")
        cov = coverage.Coverage(source=[self.mod_name], messages=True)
        cov.start()
        result = self._run_tests(test_source)
        cov.stop()
        test_metadata = dict()
        print("Running Tests completed...")
        if isinstance(result, str):
            # Return exception message
            test_metadata['compile_error'] = result
            return test_metadata
        try:
            cov.json_report(outfile=temp_json.name)
            with open(temp_json.name) as file:
                json_report = json.load(file)
            temp_json.close()
            os.remove(temp_json.name)
 
            # Prepare metadata
            test_metadata['tests_ran_n'] = result.testsRun
            test_metadata['errors'] = result.errors
            test_metadata["failures"] = result.failures
            fn = [*json_report["files"].keys()][0]
            test_metadata['executed_lines'] = json_report["files"][fn]['executed_lines']
            test_metadata['missing_lines'] = json_report["files"][fn]['missing_lines']
            test_metadata['compile_error'] = None
        except:
            test_metadata['compile_error'] = f"Make sure to import the definition from {self.mod_name} module. "\
                f"Include 'from {self.mod_name} import *' in your response."
        return test_metadata

    def _run_tests(self, test_source):
        """Helper Function for run_tests_with_coverage. Runs tests and returns results."""
        # Setup Temporary file for Test code
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=self.suffix) as temp_file:
            temp_file.write(test_source)
            temp_fn = temp_file.name
        try:
            # Try Loading Temp file as module: Checks if provided code by ChatGPT is a valid module/script
            spec = importlib.util.spec_from_file_location(os.path.basename(temp_fn)[:-3], temp_fn)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(module.__file__)
        except Exception as e:
            return traceback.format_exception_only(type(e), e)[-1]
        finally:
            # Delete temp file
            os.remove(temp_fn)

        # Set-up Tests
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(module=module)
        runner = unittest.TextTestRunner(verbosity=2, warnings=False)
        # Run Tests
        result = runner.run(test_suite)
        return result


    def _source_module(self, module:str):
        if not module.endswith(self.suffix):
            raise Exception(f"Module should be a python module with a {self.suffix} extension")
        try:
            sourced_module = importlib.import_module(self.mod_name)
        except Exception:
            raise Exception(f"Error while importing module: {module}")
        return sourced_module


