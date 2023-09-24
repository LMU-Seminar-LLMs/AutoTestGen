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

    def retrieve_func_defs(self) -> list[str]:
        return self.code_analyser.body_func_names

    def retrieve_class_defs(self) -> list[str]:
        return self.code_analyser.body_class_names
    
    def retrieve_class_methods(self, class_name: str) -> list[str]:
        class_node = self.code_analyser.body_class_nodes[
            self.code_analyser.body_class_names.index(class_name)
        ]
        method_nodes = [
            subn
            for subn in class_node.body
            if isinstance(subn, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        # Exclude properties for now.
        method_names = [
            method.name
            for method in method_nodes
            if not isinstance(
                getattr(
                    getattr(self.sourced_module, class_name), method.name
                ),
                property
            )
        ]
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
        obj_name = kwargs.get('obj_name')
        
        # Making sure that tested object is imported.
        test_lines = test.split("\n")
        import_string = f"from {self.mod_name} import {obj_name}"
        import_asterisk = f"from {self.mod_name} import *"
        if not [
            l for l in test_lines
            if l.startswith(import_string) or l == import_asterisk
        ]: 
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


    def _prepare_prompt_method(
        self,
        object_name: str,
        method_name: str
    ) -> list[dict[str, str]]:
        """
        Helper function for preparing prompt for a method of a class.
        
        Args:
            object_name (str): Name of the class.
            method_name (str): Name of the method.
        
        Returns:
            list[dict[str, str]]: List of messages.
        """
        object_description = (
            "Method Definition of a class called " + object_name
        )
        object_type = "method"
        class_node = self.code_analyser.retrieve_class_node(object_name)
        method_node = self.code_analyser.retrieve_func_node(
            object_name,
            method_name
        )
        source_code = self.retrieve_classmethod_source(
            object_name,
            method_name
        )
        if (_has_init(object_name, self.sourced_module) and
                method_name != "__init__"):
            init = self.retrieve_classmethod_source(object_name, "__init__")
        else:
            init = None
        
        class_attributes = self.code_analyser.identify_body_variables(
            class_node
        )
        class_attributes_str = "\n".join(class_attributes)
        imports_str = "\n".join(self.code_analyser.import_statements)
        constants_str = "\n".join([
            f"{k}={v}"
            for k, v in self.code_analyser.imported_constants.items()
        ])
        variables_str = "\n".join(self.code_analyser.variables)
        local_type_variables_str = "\n".join(
            [f"{k}: {v}" for k, v in self.code_analyser.local_type_variables]
        )
        relevant_calls = self.code_analyser.get_local_calls(
            method_node,
            method=True,
            class_name=object_name
        )
        local_defs_str = self.code_analyser.get_local_defs_str(relevant_calls)

        info_sheet = generate_python_info_sheet(
            object_type = object_type,
            module_name=self.mod_name,
            imports=imports_str,
            constants=constants_str,
            variables=variables_str,
            local_type_variables=local_type_variables_str,
            local_call_defs=local_defs_str,
            class_name=object_name,
            init=init,
            class_attributes=class_attributes_str
        )

        system_prompt = INITIAL_SYSTEM_PROMPT.format(
            language=self.language,
            framework=self.framework,
            obj_desc= object_description
        )

        user_prompt = INITIAL_USER_PROMPT.format(
            object_type=object_type.capitalize(),
            source_code=source_code,
            info_sheet=info_sheet
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        return messages

    def _prepare_prompt_function(
        self,
        object_name: str
    ) -> list[dict[str, str]]:
        """
        Helper function for preparing prompt for a function.
        
        Args:
            object_name (str): Name of the function.
            
        Returns:
            list[dict[str, str]]: List of messages.
        """
        object_description = "Function Definition"
        object_type = "function"
        node = self.code_analyser.retrieve_func_node(object_name)
        source_code = self.retrieve_func_source(object_name)
        
        system_prompt = INITIAL_SYSTEM_PROMPT.format(
            language=self.language,
            framework=self.framework,
            obj_desc= object_description
        )

        imports_str = "\n".join(self.code_analyser.import_statements)
        constants_str = "\n".join([
            f"{k}={v}"
            for k, v in self.code_analyser.imported_constants.items()
        ])
        variables_str = "\n".join(self.code_analyser.variables)
        local_type_variables_str = "\n".join(
            [f"{k}: {v}" for k, v in self.code_analyser.local_type_variables]
        )
        relevant_calls = self.code_analyser.get_local_calls(node)
        local_defs_str = self.code_analyser.get_local_defs_str(relevant_calls)

        info_sheet = generate_python_info_sheet(
            object_type = object_type,
            module_name=self.mod_name,
            imports=imports_str,
            constants=constants_str,
            variables=variables_str,
            local_type_variables=local_type_variables_str,
            local_call_defs=local_defs_str
        )
        
        user_prompt = INITIAL_USER_PROMPT.format(
            object_type=object_type.capitalize(),
            source_code=source_code,
            info_sheet=info_sheet
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        return messages

    def prepare_prompt(
        self,
        object_name: str,
        method_name: str=None
    ) -> list[dict[str, str]]:
        object_names = (
            self.code_analyser.body_func_names
            + self.code_analyser.body_class_names
        )
        if object_name not in object_names:
            raise ValueError(
                object_name + " not found in the module " + self.mod_name
            )
        
        # Function case
        if (
            object_name in self.code_analyser.body_func_names and
            method_name is None
        ):
            messages = self._prepare_prompt_function(object_name)
        # Method case
        elif (
            object_name in self.code_analyser.body_class_names and
            method_name is not None
        ):
            messages = self._prepare_prompt_method(object_name, method_name)
        else:
            raise ValueError("Invalid object name or method name.")
        # Might add entire class case later.
        return messages

class AstVisitor(ast.NodeVisitor):
    """
    Class for visiting AST nodes to analyse the code.
    
    Attributes:
        sourced_module (ModuleType): Sourced module.
        import_statements list[str]: List of import statements
            in the module.
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
        self.import_statements: list[str] = []
        self.modules : dict[str, str] = dict()
        self.func_names : set[str] = set()
        self.instances : dict[str, str] = dict()

    def visit_Import(self, node: ast.Import) -> None:
        """
        Handles both simple and alias imports. Statements are collected
        in import_statements. Imported moule names are collected in
        modules dict.
        Runs recursively through the tree starting from node.
        """
        if node.names:
            self.import_statements.append(ast.unparse(node))
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
        in import_statements. Imported moule names are collected in
        modules dict.
        Runs recursively through the tree starting from node.
        """
        module = node.module
        if module:
            self.import_statements.append(ast.unparse(node))
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
        fun_name = _get_function_name(node.func)
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
                    func_name = _get_function_name(node.value.func)
                    if _is_class(func_name, self.sourced_module):
                        self.instances[target.id] = func_name
                    else:
                        self.func_names.add(func_name)
            elif isinstance(target, ast.Tuple):
                # Tuple assignment with multiple targets and single value
                if isinstance(node.value, ast.Call):
                    func_name = _get_function_name(node.value.func)
                    if _is_class(func_name, self.sourced_module):
                        for target in target.elts:
                            if isinstance(target, ast.Name):
                                self.instances[target.id] = func_name
                    else:
                        self.func_names.add(func_name)
                elif isinstance(node.value, ast.Tuple):
                    # Tuple assignment with multiple targets and values
                    for tar_name, value in zip(target.elts, node.value.elts):
                        if isinstance(value, ast.Call):
                            func_name = _get_function_name(value.func)
                            if _is_class(func_name, self.sourced_module):
                                if isinstance(tar_name, ast.Name):
                                    self.instances[tar_name.id] = func_name
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
            func_name = _get_function_name(node.value.func)
            if _is_class(func_name, self.sourced_module):
                if isinstance(node.target, ast.Name):
                    self.instances[node.target.id] = func_name
        if node.value is None:
            # Hint annotation without actual value assignment
            if isinstance(node.annotation, ast.Name):
                class_name = _get_function_name(node.annotation)
            if isinstance(node.annotation, ast.Subscript):
                class_name = _get_function_name(node.annotation.slice)
            if _is_class(class_name, self.sourced_module):
                self.instances[node.target.id] = class_name
    
    def restore_visitor(self) -> None:
        """Resets visitor attributes."""
        self.import_statements = []
        self.modules = dict()
        self.func_names = set()
        self.instances = dict()

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

        # Instance of AstVisitor to analyse syntax-tree
        self.ast_visitor = AstVisitor(self.sourced_module)
        
        # Function and Class defs of the body are already identified
        # Now we visit the rest of the body nodes using the visitor
        for node in self.syntax_tree.body:
            if not isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                self.ast_visitor.visit(node)
        
        # Collect results
        # 1. Import statements.
        self.import_statements = self.ast_visitor.import_statements[:]
        
        # Local modules: modules that are part of the same package, repository
        modules = self.ast_visitor.modules.copy()
        self.modules_local = self.get_local_modules(modules)
        
        # 2. Imported constants in a single string.
        # primitives for identifying constants
        self.primitives = (
            str, int, float, complex, list, tuple, range, dict, set,
            frozenset, bool, bytes, bytearray, memoryview, type(None)
        )
        self.imported_constants = self.identify_imported_constants(
            module_asnames=[*modules.keys()]
        )
        
        # 3. Identify Body Level assignments without recursion.
        self.variables = self.identify_body_variables(self.syntax_tree)
        
        # 4. Identify local type variables.
        self.local_type_variables = self.identify_local_type_variables(
            node=self.syntax_tree,
            body_definiton_names=self.body_func_names + self.body_class_names,
            modules_local=self.modules_local
        )

        # 5. Identify body level created or from local module imported
        # class instances.
        self.body_instances = {
            k:v
            for k, v in self.ast_visitor.instances.items()
            if (
                v in self.body_class_names or
                v.split(".")[0] in self.modules_local
            )
        }

    def retrieve_class_node(self, obj_name: str) -> ast.ClassDef:
        """Returns class node given a class name"""
        return self.body_class_nodes[self.body_class_names.index(obj_name)]
    
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
        
    def get_local_modules(self, modules: dict[str, str]) -> list[str]:
        """
        Returns list of local modules:
            modules that are part of the same package, repository.

        Args:
            modules (dict[str, str]): Dictionary of imported modules.
                Keys: asnames of imported modules. [import module as name]
                Values: actual module names.

        Returns:
            list: List of local module asnames.    
        """
        module_asnames = [*modules.keys()]
        module_names = [*modules.values()]
        dir_path: str = os.path.dirname(self.sourced_module.__file__)
        # Local .py files and dirs
        local_files = [
            fn
            for fn in os.listdir(dir_path)
            if os.path.isdir(os.path.join(dir_path, fn)) or fn.endswith(".py")
        ]
        # Check if imported module is local
        modules_local = []
        for mod in module_names:
            if mod.startswith(".") or mod.split(".")[0] in local_files:
                for i, v in enumerate(module_names):
                    if v == mod:
                        # Collect module asnames
                        modules_local.append(module_asnames[i])
        return modules_local
    
    def identify_imported_constants(
        self,
        module_asnames: list[str]
    ) -> dict[str, str]:
        """
        Identifies imported constants in a module.

        Args:
            module_asnames (list): List of asnames of imported modules.
        
        Returns:
            dict: Dictionary of imported constants in the form of
                name: str(constant)
        """
        imported_constants = dict()
        for module in module_asnames:
            obj = _trace_module(module, self.sourced_module)

            if type(obj) in self.primitives:
                # type hint
                type_hint = f"{module.split('.')[-1]}: {type(obj).__name__}"
                imported_constants[type_hint] = str(obj)
        return imported_constants
    
    def identify_body_variables(
        self,
        node: Union[ast.Module, ast.ClassDef]
    ) -> list[str]:
        """Identifies body level variables in a module or class."""
        variables: list[str] = []
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
        for rest_node in rest_nodes:
            # Ignore docstrings
            if isinstance(rest_node, ast.Expr):
                if isinstance(rest_node.value, ast.Constant):
                    if isinstance(rest_node.value.value, str):
                        continue
            variables.append(ast.unparse(rest_node))
        return variables

    def identify_local_type_variables(
        self,
        node: Union[ast.Module, ast.ClassDef],
        body_definiton_names: list[str],
        modules_local: list[str]
    ) -> dict[str, str]:
        """
        Identifies local type variables in a module or class.
        
        Args:
            node (Union[ast.Module, ast.ClassDef]): Module or class node.
            body_definiton_names (list[str]): List of names of functions
                and classes defined in the module or class.
            modules_local (list[str]): List of imported local module names.

        Returns:
            dict[str, str]: Dictionary of local type variables in the
                form of {name:type}.
        """
        local_type_variables: dict[str, str] = dict()
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
        for rest_node in rest_nodes:
            if isinstance(rest_node, ast.Assign):
                if isinstance(rest_node.value, ast.Call):
                    call_name = _get_function_name(rest_node.value.func)
                    if (
                        call_name in body_definiton_names or
                        call_name in modules_local
                    ):
                        for target in rest_node.targets:
                            if isinstance(target, ast.Name):
                                local_type_variables[target.id] = type(
                                    getattr(self.sourced_module, target.id)
                                )
                            if isinstance(target, ast.Tuple):
                                for elt in target.elts:
                                    if isinstance(elt, ast.Name):
                                        local_type_variables[elt.id] = type(
                                            getattr(
                                                self.sourced_module,
                                                elt.id
                                            )
                                        )
        return local_type_variables

    def get_local_calls(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        method: bool=False,
        class_name: Union[str, None]=None
    ) -> set[str]:
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
        _ = self.ast_visitor.restore_visitor()
        self.ast_visitor.visit(node)
        call_names: list[str] = list(self.ast_visitor.func_names)
        
        # Enclosed env has priority over global
        instances = self.body_instances.copy()
        instances.update(self.ast_visitor.instances)

        # Swap instance name with associated class name in calls.
        for i, call in enumerate(call_names):
            splits = call.split('.')
            if len(splits) > 1:
                if method:
                    # If it is called inside a class definition swap indicator
                    # [self, cls, ...] with class name.
                    indicator = node.args.args[0].arg
                    if splits[0] == indicator:
                        splits[0] = class_name
                else:
                    # Else swap instance name with class name.
                    if splits[0] in [*instances.keys()]:
                        splits[0] = instances[splits[0]]
                # Reconstruct call name
                call_names[i] = '.'.join(splits)
        local_classes = list(self.modules_local) + self.body_class_names
        local_functions = list(self.modules_local) + self.body_func_names
        local_calls = [
            nm
            for nm in call_names
            if (
                (nm in local_functions or nm.split(".")[0] in local_classes)
                and nm != node.name
            )
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
            if _is_method(call, self.sourced_module):
                # If call is a class method call
                local_defs += (
                    "Method Definition for "
                    + call
                    + ":\n" 
                    + _trace_call(call, self.sourced_module)
                    + "\n"
                )
                has_init = _has_init(call, self.sourced_module)
                if has_init and call.split(".")[-1] != "__init__":
                    local_defs += (
                        "Associated class __init__ definition:"
                        + "\n"
                        + _get_init(call, self.sourced_module)
                        + "\n"
                    )
            else:
                source_code = _trace_call(call, self.sourced_module)
                if source_code:
                # If it is simple local function call
                    local_defs += (
                        "Definition for "
                        + call
                        + ":\n"
                        + source_code
                        + "\n"
                    )
        return local_defs


# Helper Functions
def _is_method(call_name: str, sourced_module: ModuleType) -> bool:
    """
    Helper Function checks if a call is a class method
    
    Args:
        call_name (str): Name of the cal
        sourced_module (ModuleType): Sourced module to search in.
    
    Returns:
        bool: True if call is a class method.
    """
    submodules = call_name.split('.')
    for submodule in submodules[:-1]:
        try:
            sourced_module = getattr(sourced_module, submodule)
        except:
            return False
    try:
        method_attr = getattr(sourced_module, submodules[-1])
    except:
        return False
    
    if inspect.isclass(sourced_module) and callable(method_attr):
        return True
    return False
    
def _has_init(call_name: str, sourced_module: ModuleType) -> bool:
    """
    Checks if a class associated to call_name has an __init__ method.

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
    
def _is_class(call_name: str, sourced_module: ModuleType) -> bool:
    """
    Checks if a function call is a class instance creation.
    
    Args:
        call_name (str): Name of the call.
        sourced_module (ModuleType): Sourced module.
    
    Returns:
        bool: True if call is a class instance creation.
    """
    submodules = call_name.split('.')
    if (
        call_name in dir(sourced_module)
        or submodules[0] in dir(sourced_module)
    ):
        if len(submodules) != 1:
            call_name = submodules[-1]
            for submodule in submodules[:-1]:
                sourced_module = getattr(sourced_module, submodule)
        if sourced_module is not None:
                try:
                    return inspect.isclass(getattr(sourced_module, call_name))
                except:
                    pass
    return False
    
def _get_init(call_name: str, sourced_module: ModuleType) -> Union[str, None]:
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
    if not _has_init(call_name, sourced_module):
        return None
    return inspect.getsource(getattr(class_object, '__init__'))

def _trace_module(module_name: str, sourced_module: ModuleType) -> ModuleType:
    """
    Traces a module recursively until reaching the last submodule.
    
    Args:
        module_name (str): Name of the module.
        sourced_module (ModuleType): Sourced module.
    
    Returns:
        ModuleType: last submodule.
    """
    if not module_name:
        return sourced_module
    submodules = module_name.split('.')
    for submodule in submodules:
        sourced_module = getattr(sourced_module, submodule)
    return sourced_module

def _trace_call(
    call_name: str,
    sourced_module: ModuleType
) -> Union[str, None]:
    """
    Helper Function traces a call recursively until reaching
    the function, method definition itself and returns its source code.

    Args:
        call_name (str): Name of the call.
        sourced_module (ModuleType): Sourced module.

    Returns:
        str: source code of the definiton.
    """
    submodules = call_name.split('.')
    for submodule in submodules:
        try:
            sourced_module = getattr(sourced_module, submodule)
        except:
            return None
    return inspect.getsource(sourced_module)

def _get_function_name(node: ast.expr) -> str:
    """
    Takes an ast node and returns the name of the function or method
    through recursion.
    
    Args:
        node: ast node.
    
    Returns:
        str: Function name.
    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return _get_function_name(node.value) + '.' + node.attr
    elif isinstance(node, ast.Call):
        return _get_function_name(node.func)
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Subscript):
        return _get_function_name(node.value)