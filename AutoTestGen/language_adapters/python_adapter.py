from .base_adapter import BaseAdapter
import ast, os, inspect, re
import importlib, importlib.util
from typing import Union
from types import ModuleType
from ..templates import generate_python_info_sheet
from ..templates import INITIAL_SYSTEM_PROMPT, INITIAL_USER_PROMPT


class PythonAdapter(BaseAdapter):
    def __init__(self, module: str):
        super().__init__("python", module)
        self.suffix = ".py"
        self.framework = "unittest"
        if module.startswith("/"): 
            self.mod_name = module[1:-3].replace('/', '.')
        else:
            self.mod_name = module[:-3].replace('/', '.')
        self.sourced_module = self._source_module(module)
        self.code_analyser = CodeAnalyser(self.sourced_module)

    def retrieve_module_source(self) -> str:
        return inspect.getsource(self.sourced_module)

    def retrieve_func_defs(self) -> list:
        return self.code_analyser.body_func_names

    def retrieve_class_defs(self) -> list:
        return self.code_analyser.body_class_names
    
    def retrieve_class_methods(self, class_name: str) -> list:
        class_node = self.code_analyser.body_class_nodes[
            self.code_analyser.body_class_names.index(class_name)
        ]
        method_nodes = [
            subn
            for subn in class_node.body
            if isinstance(subn, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        method_names = [method.name for method in method_nodes]
        return method_names

    def retrieve_func_source(self, func_name: str) -> str:
        return inspect.getsource(getattr(self.sourced_module, func_name))
    
    def retrieve_class_source(self, class_name: str) -> str:
        return inspect.getsource(getattr(self.sourced_module, class_name))
    
    def retrieve_classmethod_source(
        self,
        class_name: str,
        method_name: str
    ) -> str:
        return inspect.getsource(
            getattr(getattr(self.sourced_module, class_name), method_name)
        )

    def check_reqs_in_container(self, container) -> Union[str, None]:
        # Check python version.
        vers = container.exec_run("python3 --version").output.decode("utf-8")
        major, minor = re.search(r"(\d+\.\d+)", vers).group(1).split(".")
        if int(major) < 3 or int(minor) < 9:
            return f"Python version should be >= 3.9, it is {major}.{minor}"
        
        # check if coverage package is installed.
        if container.exec_run("coverage --version").exit_code != 0:
            return "coverage library is not installed in the container."
        
        # Check if all necessary dependencies are installed.
        check_import = container.exec_run(
            f"python3 -c 'import {self.mod_name}'",
            workdir="/tmp/autotestgen/"
        )
        if check_import.exit_code != 0:
            resp: str = check_import.output.decode("utf-8").split("\n")
            if any(
                [ln for ln in resp if ln.startswith("ModuleNotFoundError")]
            ):
                return (
                    "There is a missing dependency in the container. "
                    "Please intall it first.\n" 
                    + "\n".join(resp)
                )
            else:
                return (
                    "Sourcing module in the container failed "
                    "with the following error:\n"
                    + "\n".join(resp)
                )
        return None

    def postprocess_resp(self, test: str, **kwargs) -> str:
        """
        Postprocesses the test string returned by the API.

        Args:
            test (str): The response string returned
                by the OpenAI API.
            **kwargs:
                obj_name (str): Name of the obj (class, func) to test.
        """
        obj_name= kwargs.get('obj_name')
        
        # Making sure that tested object is imported.
        test_lines = test.split("\n")
        import_string = f"from {self.mod_name} import {obj_name}"
        import_asterisk = f"from {self.mod_name} import *"
        if (not import_string in test_lines and
             not import_asterisk in test_lines):
            test_lines.insert(0, import_string)

        # Making sure script is only executed when ran from main.
        if (
            not "if __name__ == '__main__':" in test_lines
            and not 'if __name__ == "__main__":' in test_lines
        ):
            if "unittest.main()" in test_lines:
                test_lines.remove("unittest.main()")
            test_lines.append("if __name__ == '__main__':")
            test_lines.append("    unittest.main()")

        # GPT-4 very often wraps response in ```python``` code block
        # and adds extra explanation lines even though
        # explicilty asked not to
        if "```python" in test_lines:
            start_index = test_lines.index("```python")
            end_index = test_lines.index("```")
            test_lines = test_lines[start_index+1:end_index]
        return "\n".join(test_lines)

    def _source_module(self, module: str) -> ModuleType:
        """
        Helper function for sourcing a module from a path.

        Parameters:
            module (str): Path to the module.
        
        Returns:
            ModuleType: Sourced module.
        
        Raises:
            Exception: If the module is not a python file
                or cannot be imported.
        """
        if not module.endswith(self.suffix):
            raise Exception(
                f"Module should be a python file with {self.suffix} extension"
            )
        try:
            sourced_module = importlib.import_module(self.mod_name)
        except Exception:
            print(f"Error while importing module: {module}")
            raise
        return sourced_module


    def prepare_prompt(self, obj_name: str, method_name: str=None):
        objs = (
            self.code_analyser.body_func_names
            + self.code_analyser.body_class_names
        )

        if obj_name not in objs:
            raise ValueError(
                obj_name + " not found in the module " + self.mod_name
            )
        
        # Two cases: Function or class methods
        if (
            obj_name in self.code_analyser.body_func_names and 
            method_name is None
        ):
            
            obj_type = "function"
            obj_desc = "Function Definition"
            node = self.code_analyser.retrieve_func_node(obj_name)
            source_code = self.retrieve_func_source(obj_name)
            relevant_calls = self.code_analyser.get_local_calls(node)
            local_call_defs = self.code_analyser.get_local_defs_str(
                relevant_calls
            )

            info_sheet = generate_python_info_sheet(
                obj_type = obj_type,
                module_name=self.mod_name,
                imports=self.code_analyser.imports_string,
                constants=self.code_analyser.imported_constants_str,
                variables=self.code_analyser.variables_string,
                local_call_defs=local_call_defs
            )
        
        elif (obj_name in self.code_analyser.body_class_names and
               method_name is not None):
            obj_type = "class"
            obj_desc = "Method Definition of a class called " + obj_name
            class_node = self.code_analyser.retrieve_class_node(obj_name)
            method_node = self.code_analyser.retrieve_func_node(
                obj_name,
                method_name
            )
            source_code = self.retrieve_classmethod_source(
                obj_name,
                method_name
            )
            
            has_init = self.code_analyser._has_init(
                obj_name,
                self.sourced_module
            )

            if has_init and method_name != "__init__":
                init = self.retrieve_classmethod_source(obj_name, "__init__")
            else:
                init = ''

            class_attributes = self.code_analyser.get_body_variables_str(
                class_node
            )
            relevant_calls = self.code_analyser.get_local_calls(
                method_node,
                method=True,
                class_name=obj_name
            )

            local_call_defs = self.code_analyser.get_local_defs_str(
                relevant_calls
            )

            info_sheet = generate_python_info_sheet(
                obj_type = obj_type,
                module_name=self.mod_name,
                imports=self.code_analyser.imports_string,
                constants=self.code_analyser.imported_constants_str,
                variables=self.code_analyser.variables_string,
                local_call_defs=local_call_defs,
                class_name=obj_name,
                init=init,
                class_attributes=class_attributes
            )

        
        # Prepare system PROMPT
        system_prompt = INITIAL_SYSTEM_PROMPT.format(
            language=self.language,
            framework=self.framework,
            obj_desc= obj_desc
        )

        # Prepare initial user PROMPT
        user_prompt = INITIAL_USER_PROMPT.format(
            obj_type= "Function "if obj_type == "function" else "Method",
            source_code=source_code,
            info_sheet=info_sheet
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        return messages


class AstVisitor(ast.NodeVisitor):
    """
    Class for visiting AST nodes to analyse the code.
    
    Attributes:
        sourced_module (ModuleType): Sourced module.
        imports_string (str): String of all import statements combined.
        modules (dict[str, str]): Dictionary of imported modules.
            Keys: asnames of imported modules. [import module as name]
            Values: actual module names.
        func_names (set): set of names of called objects: 
            function, classes, classmethods, ...
        instances (dict): Dictionary of created class instances inside
            the module. Keys: instance names, Values: class names.
    """
    def __init__(self, sourced_module: ModuleType):
        self.sourced_module = sourced_module
        self.imports_string : str = ''
        self.modules : dict[str, str] = dict()
        self.func_names : set = set()
        self.instances : dict = dict()

    def visit_Import(self, node: ast.Import) -> None:
        """
        Handles both simple and alias imports. Statements are collected
        in imports_string. Imported moule names are collected in
        modules dict.
        Runs recursively through the tree starting from node.
        """
        self.imports_string += (ast.unparse(node) + '\n')
        for alias in node.names:
            if alias.asname:
                # Alias import
                self.modules[alias.asname] = alias.name
            else:
                # Simple import
                self.modules[alias.name] = alias.name
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """
        Handles import from statements. Statements are collected
        in imports_string. Imported moule names are collected in
        modules dict.
        Runs recursively through the tree starting from node.
        """
        module = node.module
        if module:
            self.imports_string += (ast.unparse(node) + '\n')
            for alias in node.names:
                # From import with alias
                if alias.asname:
                    self.modules[alias.asname] = module
                else:
                    # Simple from import
                    if alias.name != '*':
                        self.modules[alias.name] = module
                    # From import with asterisk
                    else:
                        # dynamically import module
                        module_asterisked = importlib.import_module(module)
                        
                        # Exclude builtins and module members of imported mod.
                        module_members = inspect.getmembers(
                            module_asterisked,
                            inspect.ismodule
                        )
                        module_names = [name for name, _ in module_members]

                        self.modules.update(
                            {name: module
                             for name in dir(module_asterisked)
                             if not name.startswith('__') and 
                                name not in module_names}
                        ) 
        else:
            # Rlative ImportFrom case which is equivalent to simple import.
            self.visit_Import(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """
        Collects function names [names of called objects]
        in 'func_names' set.
        Runs recursively through the tree starting from node.
        """
        fun_name = self._get_function_name(node.func)
        if fun_name:
            self.func_names.add(fun_name)                
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Searches for class instance creations and collects them in 
        in self.instances attribute to track their methods later.
        """
        for target in node.targets:
            # Simple single target:call assignment
            if isinstance(target, ast.Name):
                if isinstance(node.value, ast.Call):
                    func_name = self._get_function_name(node.value.func)
                    if self._is_class(func_name, self.sourced_module):
                        self.instances[target.id] = func_name
                    else:
                        self.func_names.add(func_name)

            elif isinstance(target, ast.Tuple):
                # Tuple assignment with multiple targets
                for target_name, value in zip(target.dims, node.value.dims):
                    if isinstance(value, ast.Call):
                        func_name = self._get_function_name(value.func)
                        if self._is_class(func_name, self.sourced_module):
                            self.instances[target_name.id] = func_name
                        else:
                            self.func_names.add(func_name)
    
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """
        Searches for class instance creations and collects them in 
        in self.instances attribute to track their methods later.
        Handles special case of annotated assignment.
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

    def _is_class(self, func_name: str, sourced_module: ModuleType) -> bool:
        """Checks if a function call is a class instance creation."""
        submodules = func_name.split('.')
        if (
            func_name in dir(sourced_module) or 
            submodules[0] in dir(sourced_module)
        ):
            if len(submodules) != 1:
                func_name = submodules[-1]
                for submodule in submodules[:-1]:
                    sourced_module = getattr(sourced_module, submodule)
            if sourced_module is not None:
                return inspect.isclass(getattr(sourced_module, func_name))
        return False

    def _get_function_name(self, node: ast.expr) -> str:
        """
        Tracks down object name that was called through recursion.
        
        Args:
            node: ast node.
        
        Returns:
            str: Function name.
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_function_name(node.value) + '.' + node.attr
        elif isinstance(node, ast.Call):
            return self._get_function_name(node.func)
        elif isinstance(node, ast.Constant):
            return node.value

class CodeAnalyser:
    """Class for analysing the code of a module."""
    def __init__(self, sourced_module: ModuleType):
        """
        Args:
            sourced_module (ModuleType): Sourced module.
        """
        # Start-up
        self.sourced_module = sourced_module
        self.source_code = inspect.getsource(sourced_module)
        self.syntax_tree = ast.parse(self.source_code)

        # Body Class Nodes
        self.body_class_nodes = [
            subn 
            for subn in self.syntax_tree.body
            if isinstance(subn, ast.ClassDef)
        ]
        self.body_class_names = [node.name for node in self.body_class_nodes]
        
        # Body Func Nodes
        self.body_func_nodes = [
            subn
            for subn in self.syntax_tree.body
            if isinstance(subn, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.body_func_names = [node.name for node in self.body_func_nodes]

        # Instance of AstVisitor to go through syntax-tree
        self.ast_visitor = AstVisitor(self.sourced_module)
        
        # Function and Class definitons of the body are already identified
        # Now we visit the rest of the body nodes using the visitor
        for node in self.syntax_tree.body:
            if not isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                self.ast_visitor.visit(node)
        
        # Collect results
        # 1. Import statements in a single string + names of imported modules
        self.imports_string = self.ast_visitor.imports_string
        self.modules_all = [*self.ast_visitor.modules.keys()]
        
        # Local modules: modules that are part of the same package, repository
        self.modules_local = self.get_local_modules(self.modules_all)
        
        # 2. Imported constants in a single string.
        # primitives for identifying constants
        self.primitives = (
            str, int, float, complex, list, tuple, range, dict, set,
            frozenset, bool, bytes, bytearray, memoryview, type(None)
        )
        self.imported_constants_str = self.get_imported_constants_str(
            self.modules_all
        )
        # 3. Body Level assignments without recursion.
        self.variables_string = self.get_body_variables_str(self.syntax_tree)

        # 4. Identify body level created or from local module imported
        # class instances.
        self.body_instances = {
            k:v
            for k, v in self.ast_visitor.instances.items()
            if (
                v in self.body_class_names or
                v.split(".")[0] in self.modules_local
            )
        }
        
    def get_local_modules(self, modules_all: list) -> list:
        """
        Returns list of local modules:
            modules that are part of the same package, repository

        Args:
            modules_all (list): List of asnames of imported modules.

        Returns:
            list: List of local module asnames.    
        """
        # Actual names of imported modules
        imported_mods = [*self.ast_visitor.modules.values()]
        dir_path = os.path.dirname(self.sourced_module.__file__)
        # Local .py files and dirs
        local_files = [
            fn
            for fn in os.listdir(dir_path)
            if os.path.isdir(os.path.join(dir_path, fn)) or fn.endswith(".py")
        ]
        # Check if imported module is local
        modules_local = []
        for mod in imported_mods:
            if mod.startswith(".") or mod.split(".")[0] in local_files:
                for i, v in enumerate(imported_mods):
                    if v == mod:
                        # Collect module asnames
                        modules_local.append(modules_all[i])
        return modules_local
    
    def get_imported_constants_str(self, modules_all: list) -> str:
        """
        Returns string of imported constants
        
        Args:
            modules_all (list): List of asnames of imported modules.
        
        Returns:
            str: containing all imported constants with their values.
        """
        imported_consts_str = ''
        for module in modules_all:
            traced_module = self._trace_module(module, self.sourced_module)
            obj = getattr(traced_module, module.split(".")[-1])
            if type(obj) in self.primitives:
                imported_consts_str += (module + "=" + str(obj) + "\n")
        return imported_consts_str
    
    def get_body_variables_str(
        self,
        node: Union[ast.Module, ast.ClassDef]
    ) -> None:
        """
        Returns string of body level assignments and additionally
        looks for declarations of variable types which are local and
        unknown to the GPT model.
        """
        variables_string = ''
        decleared_types = ''
        rest_nodes = [
            subn
            for subn in node.body
            if not isinstance(subn, (
                ast.Import,
                ast.ImportFrom,
                ast.FunctionDef,
                ast.ClassDef,
                ast.AsyncFunctionDef
            ))
        ]
        
        body_defs = self.body_func_names + self.body_class_names
        for rest_node in rest_nodes:
            # Ignore docstrings
            if isinstance(rest_node, ast.Expr):
                if isinstance(rest_node.value, ast.Constant):
                    if isinstance(rest_node.value.value, str):
                        continue
            variables_string += (ast.unparse(rest_node) + '\n')
            # Body Level assignments
            if isinstance(rest_node, ast.Assign):
                if isinstance(rest_node.value, ast.Call):
                    # Unobvious local type variable assignments.
                    call_name = self.ast_visitor._get_function_name(
                        rest_node.value.func
                    )
                    if (
                        call_name in body_defs or
                        call_name in self.modules_local
                    ):
                        for name in rest_node.targets:
                            decleared_types += (
                                name.id 
                                + ": " 
                                + type(getattr(self.sourced_module, name.id))
                                + "\n"
                            )
        if decleared_types != '':
            final_string = (
                variables_string
                + "Additionally variable types for body-decleared variables "
                + "whose types are not obvious:\n"
                + decleared_types
            )
        else:
            final_string = variables_string
        return final_string

    def retrieve_func_node(
        self,
        obj_name: str,
        method: Union[str, None]=None
    ) -> Union[ast.FunctionDef, ast.AsyncFunctionDef]:
        """
        Returns function node given a function name or 
        (class name and method name).
        
        Args:
            obj_name (str): Name of the object (function, class).
            method (str, optional): Name of the method if obj_name
                is a class. Defaults to None.

        Returns:
            Union[ast.FunctionDef, ast.AsyncFunctionDef]: node.
        """
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

    def retrieve_class_node(self, obj_name: str) -> ast.ClassDef:
        """Returns class node given a class name"""
        return self.body_class_nodes[self.body_class_names.index(obj_name)]

    def get_local_calls(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        method: bool=False,
        class_name: Union[str, None]=None
    ) -> set:
        """
        Returns all local calls inside a function or method definition.

        Args:
            node (Union[ast.FunctionDef, ast.AsyncFunctionDef]): 
                Function or method node.
            method (bool, optional): If True, the node is a method.
                Defaults to False.
            class_name (Union[str, None], optional): Name of the class
                if node is a method. Defaults to None.

        Returns:
            set: Set of local calls inside the function or method
                definition.
        """
        # Restore the visitor and collect function calls inside the node.
        self.ast_visitor.func_names = set()
        self.ast_visitor.instances = {}
        self.ast_visitor.visit(node)
        call_names: list[str] = list(self.ast_visitor.func_names)
        
        # Enclosed env has priority over global
        instances = self.body_instances.copy()
        instances.update(self.ast_visitor.instances)

        # Swap instance name with associated class name in calls.
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
            nm
            for nm in call_names
            if nm in local_functions or nm.split(".")[0] in local_classes
        ]
        return set(local_calls)

    def get_local_defs_str(self, local_calls: set[str]) -> str:
        """
        Returns string of local function and method definitions used
        in the definition of the function or method under test.

        Args:
            local_calls (set[str]): Set of local calls inside the
                function or method under test.

        Returns:
            str: String of local function and method definitions used
                in the definition of the function or method under test.
        """
        local_defs = ''
        for call in local_calls:
            if self._is_method(call, self.sourced_module):
                # If call is a class method call
                local_defs += (
                    "Method Definition for "
                    + call
                    + ":\n" 
                    + self._trace_call(call, self.sourced_module)
                    + "\n"
                )
                has_init = self._has_init(call, self.sourced_module)
                if has_init and call.split(".")[-1] != "__init__":
                    local_defs += (
                        "Associated class __init__ definition:"
                        + "\n"
                        + self._get_init(call, self.sourced_module)
                        + "\n"
                    )
                else:
                    # If it is simple local function call
                    local_defs += (
                        "Definition for "
                        + call
                        + ":\n"
                        + self._trace_call(call, self.sourced_module)
                        + "\n"
                    )
        return local_defs

    def _is_method(self, call_name: str, sourced_module: ModuleType) -> bool:
        """Helper Function checks if a call is a class method"""
        submodules = call_name.split('.')
        for submodule in submodules[:-1]:
            try:
                sourced_module = getattr(sourced_module, submodule)
            except:
                return False
        if (
            inspect.isclass(sourced_module)
            and callable(getattr(sourced_module, submodules[-1]))
        ):
            return True
        return False
    
    def _has_init(
        self,
        call_name: str,
        sourced_module: ModuleType
    ) -> bool:
        """
        Checks if a class associated to call_name has an __init__
            method definition.

        Args:
            call_name (str): Name of the call [method name].
            sourced_module (ModuleType): Sourced module.

        Returns:
            bool: True if class has __init__ method definition.
        """
        submodules = call_name.split('.')
        class_name = submodules[0]
        try:
            has_init = inspect.isfunction(
                getattr(getattr(sourced_module, class_name), "__init__")
            )
        except:
            return False
        return has_init
    
    def _get_init(
        self,
        call_name: str,
        sourced_module: ModuleType
    ) -> str:
        """
        Given a method call name, returns corresponding class 
        __init__ definition.

        Args:
            call_name (str): Name of the method call.
            sourced_module (ModuleType): Sourced module.
        
        Returns:
            str: source code of the __init__ definition.
        """
        submodules = call_name.split('.')
        class_object = getattr(sourced_module, submodules[0])
        return inspect.getsource(getattr(class_object, '__init__'))

    def _trace_module(
        self,
        module_name: str,
        sourced_module: ModuleType
    ) -> ModuleType:
        """
        Traces a module recursively until reaching the last submodule.
        
        Args:
            module_name (str): Name of the module.
            sourced_module (ModuleType): Sourced module.
        
        Returns:
            ModuleType: last submodule.
        """
        submodules = module_name.split('.')
        for submodule in submodules[:-1]:
            sourced_module = getattr(sourced_module, submodule)
        return sourced_module
    
    def _trace_call(
        self,
        call_name: str,
        sourced_module: ModuleType
    ) -> str:
        """
        Helper Function traces a call recursively until reaching
        the function, method definition itself.

        Args:
            call_name (str): Name of the call.
            sourced_module (ModuleType): Sourced module.

        Returns:
            str: source code of the definiton.
        """
        submodules = call_name.split('.')
        for submodule in submodules:
            sourced_module = getattr(sourced_module, submodule)
        return inspect.getsource(sourced_module)