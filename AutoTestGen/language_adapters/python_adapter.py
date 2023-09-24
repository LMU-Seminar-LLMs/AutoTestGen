
from .base_adapter import BaseAdapter
import ast
import sys
import inspect
from typing import Union

class SourcingError(Exception):
    def __init__(self, message):
        super().__init__(message)

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
                        if self._check_func_name(func_name):
                            self.instances[target_name.id] = func_name
            
            elif isinstance(target, ast.Name):
                if isinstance(node.value, ast.Call):
                    func_name = self.get_function_name(node.value.func)
                    if self._check_func_name(func_name):
                        self.instances[target.id] = func_name
    
    def visit_AnnAssign(self, node):
        if isinstance(node.value, ast.Call):
            func_name = self.get_function_name(node.value.func)
            if self._check_func_name(func_name):
                self.instances[node.traget.id] = func_name
        if node.value is None:
            # Case of annotations
            if isinstance(node.annotation, ast.Name):
                class_name = self.get_function_name(node.annotation)
            if isinstance(node.annotation, ast.Subscript):
                class_name = self.get_function_name(node.annotation.slice)
            if self._check_func_name(class_name):
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
    def __init__(self, library, module: str, testing_framework="unittest"):
        super().__init__(language="python", testing_framework=testing_framework)
        self.library = library

        # Start-up
        self.sourced_module = self._source_module(module)
        self.source_code = self._get_module_code(module)
        self.syntax_tree = self._build_ast(self.source_code)
        
        # Body
        self.local_modules = self._get_local_modules(self.syntax_tree)
        self.body_class_nodes = self._get_body_class_nodes(self.syntax_tree)
        self.body_func_nodes = self._get_body_func_nodes(self.syntax_tree)
        
        # primitives for identifying constants
        primitives = (int, str, bool, )
        # {instance:class}
        self.body_instances = self._get_body_instances(self.syntax_tree)
        self.body_funcs = [node.name for node in self.body_func_nodes]
        self.body_classes = [node.name for node in self.body_class_nodes]
    
    def _source_module(self, module:str):
        # Locally sources the module
        try:
            sourced_module = __import__(module)
        except Exception as e:
            raise SourcingError(f"Sourcing Failed, with: {e}")
        return sourced_module
        
    def _get_module_code(self, module:str):
        if not module.endswith(".py"):
            raise Exception("Module should be a python module with a .py extension")
        with open(module, "r") as file:
            source_code = file.read()
        return source_code

    def _build_ast(self, source_code:str):
        return ast.parse(source_code)
    
    def get_imports_string(self, module_ast: ast.Module):
        # Returns import statements together in one string
        import_visitor = ImportVisitor()
        import_visitor.visit(module_ast)
        imports_string = import_visitor.import_string
        return imports_string
    
    def _get_imported_constants(self):
        imported_consts_str = ''
        for module in self.local_modules:
            if type(getattr(self.sourced_module, module)) in self.primitives:
                imported_consts_str += f'\n{module} = {getattr(self.sourced_module, module)}'
        return imported_consts_str

    
    def _get_local_modules(self, module_ast: ast.Module):
        # Identifies local modules, returns list of strings (module names)
        import_visitor = ImportVisitor()
        import_visitor.visit(module_ast)
        # Extract asnames
        imported_mods = [*import_visitor.modules.values()]
        local_modules = set()
        for mod in imported_mods:
            name_check = mod.startswith(".") or mod.startswith(f"{self.library}.") or mod == {self.library}
            mod_sys = sys.modules[mod]
            package_check = (mod_sys.__package__ == '')
            # Might not be a robust check
            loader_check = f"{type(mod_sys.__loader__).__module__}.{type(mod_sys.__loader__).__qualname__}" == '_frozen_importlib_external.SourceFileLoader'
            if (name_check) or (package_check and loader_check):
                local_modules.add([*import_visitor.keys()][imported_mods.index(mod)])
        return local_modules

    def _get_body_func_nodes(self, node: Union[ast.Module, ast.ClassDef]):
        func_nodes = [subnode for subnode in node.body if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef))]
        return func_nodes

    def _get_body_class_nodes(self, node: Union[ast.Module, ast.ClassDef]):
        class_nodes = [subnode for subnode in node.body if isinstance(subnode, ast.ClassDef)]
        return class_nodes

    def _get_body_constants_str(self, node: Union[ast.Module, ast.ClassDef]):
        constants_string = ''
        assign_nodes = [subnode for subnode in node.body if isinstance(subnode, (ast.Assign, ast.AnnAssign, ast.AugAssign))]
        for assgn_node in assign_nodes:
            if not isinstance(assgn_node.value, ast.Call):
                constants_string += f'\n{ast.unparse(assgn_node)}'
        return constants_string
    
    def _get_body_instances(self, module_ast: ast.Module):
        # Called from ast.Module on body returns dict{instance:class}
        call_visitor = CallVisitor(self.source_module)
        for node in module_ast.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                call_visitor.visit(node)
        instances_filtered = {key: value 
                              for key, value in call_visitor.instances.items()
                              if value in self.body_classes or value.split(".")[0] in self.local_modules}
        return instances_filtered
    
    def _get_relevant_calls(self, node: ast.FunctionDef, method=False, class_name=None):
        # Returns relevant function calls and instance:class paris from enclosed enviornment
        call_visitor = CallVisitor(self.sourced_module)
        call_visitor.visit(node)
        body_defs = self.body_funcs + self.body_classes
        call_names = call_visitor.func_names
        instances = call_visitor.instances
        # Swap instance name with associated class name in calls
        for i, call in enumerate(call_names):
            splits = call.split('.')
            if splits[0] in [*instances.keys()]:
                splits[0] = instances[splits[0]]
                local_calls[i] = "".join(splits)
            if method:
                indicator = node.args.args[0].arg
                if splits[0] == indicator:
                    splits[0] = class_name
                    local_calls[i] = "".join(splits)
        local_calls = set([name for name in call_names if (name in body_defs) or name.split(".")[0] in self.local_modules])
        return local_calls

    def prepare_prompt(self, name: str, method_name=None):
        n = 0
        if name not in self.body_funcs + self.body_classes:
            raise ValueError(f"There is no class or function definition called: {name} in the {self.module}")
        elif name in self.body_funcs:
            messages = self._prepare_prompt_func(name)
        elif name in self.body_classes:
            messages = self._prepare_prompt_class(name, method_name)
        return messages

    def _prepare_prompt_func(self, name:str):
        n = 0
        imports_string = self.get_imports_string(self.syntax_tree)
        constants_string = self._get_body_constants_str(self.syntax_tree)
        node = self.body_func_nodes[self.body_funcs.index(name)]

        # System
        system_content = f'Generate high-quality comprehensive Unit-Tests in {self.language} '\
            f'using {self.framework} library for provided Function Definiton. '\
            f'Next to the Function Definiton you will be provided with numbered INFO Sheet that might be useful in generating finer Unit-Tests. '\
            f'Your renspose should be just {self.language} code without explanation.'
        
        # INFO Sheet
        user_content = f'Function Definition:\n{ast.unparse(node)}\nINFO Sheet:'
        # INFO Sheet: Imports
        if imports_string != '':
            user_content = f'{user_content}\n{n + 1}. '\
                'Following imports were made into the namespace in which '\
                f'given Fuction Definition was defined:{imports_string}'
        # INFO Sheet: Constants
        if constants_string != '':
            user_content = f'{user_content}\n{n + 1}. '\
                'Following Constants were defined into the namespace in which '\
                f'given Fuction Definition was defined:{constants_string}'

        # INFO Sheet: Definitions of calls of functions and methods defined locally
        local_calls = self._get_relevant_calls(node)
        if not len(local_calls):
            for call in local_calls:
                if self._is_method(call, self.sourced_module):
                    user_content = f'{user_content}\n{n + 1}. '\
                        f'Method Definition for {call}:\n{self._trace_call(call, self.sourced_module)}'
                    if self._has_init(call, self.sourced_module):
                        user_content = f"{user_content}\n'Associated class __init__ definition:\n{self._get_init(call, self.sourced_module)}"
                else:
                    user_content = f'{user_content}\n{n + 1}. '\
                        f'Definiton for {call}:\n{self._trace_call(call, self.sourced_module)}'
        messages = [
            {'role': 'system', 'content': system_content},
            {'role': 'user', 'content': user_content}
        ]
        return messages

    def _prepare_prompt_class(self, name: str, method_name):
        n = 0
        imports_string = self.get_imports_string(self.syntax_tree)
        constants_string = self._get_body_constants_str(self.syntax_tree)
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
            
            # System Prompt
            system_content = f'Generate high-quality comprehensive Unit-Tests in {self.language} '\
                f'using {self.framework} library for provided Classmethod Definiton of a class called: {class_node.name}. '\
                f'Next to the Classmethod Definiton you will be provided with numbered INFO Sheet that might be useful in generating finer Unit-Tests. '\
                f'Your renspose should be just {self.language} code without explanation.'

            # INFO Sheet: ClassName
            user_content = f'Classmethod Definition:\n{ast.unparse(node)}\nINFO Sheet:\n'\
                f'{n+1}. Class name: {class_node.name}'
            
            # INFO Sheet: Imports
            if imports_string != '':
                user_content = f'{user_content}\n{n + 1}. '\
                    'Following imports were made into the namespace in which '\
                    f'given Class was defined:{imports_string}'

            # INFO Sheet: Constants          
            if constants_string != '':
                user_content = f'{user_content}\n{n + 1}. '\
                    'Following Constants were defined into the namespace in which '\
                    f'given Class was defined:{constants_string}'
            
            # INFO Sheet: Attributes
            if attributes_str != '':
                user_content = f'{user_content}\n{n + 1}. '\
                    f'Class contains following attributes:{constants_string}'
            
            # INFO Sheet: __init__ if avaliable
            if '__init__' in method_names and node.name != '__init__':
                user_content = f'{user_content}\n{n + 1}. '\
                    f"Definition of Class __init__:\n{ast.unparse(method_nodes[method_names.index('__init__')])}"
            
            # INFO Sheet: Definitions of calls of functions and methods defined locally
            local_calls = self._get_relevant_calls(node, method=True, class_name=node.name)
            if not len(local_calls):
                for call in local_calls:
                    if self._is_method(call, self.sourced_module):
                        user_content = f'{user_content}\n{n + 1}. '\
                            f'Method Definition for {call}:\n{self._trace_call(call, self.sourced_module)}'
                        if self._has_init(call, self.sourced_module, omit=class_node.name):
                            user_content = f"{user_content}\n'Associated class __init__ definition:\n{self._get_init(call, self.sourced_module)}"
                    else:
                        user_content = f'{user_content}\n{n + 1}. '\
                            f'Definiton for {call}:\n{self._trace_call(call, self.sourced_module)}'

        messages = [
            {'role': 'system', 'content': system_content},
            {'role': 'user', 'content': user_content}
        ]
        return messages
    
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


    def compute_coverage():
        pass
    
    def run_tests():
        pass
        



        