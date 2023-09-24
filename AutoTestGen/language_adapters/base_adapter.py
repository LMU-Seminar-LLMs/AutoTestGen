import abc
from typing import Union

class BaseAdapter(abc.ABC):
    """
    Base class for language adapters. All the language adapters
    should fullfill the requirements of this class.

    Attributes:
        language (str): Programming language [Python, R, ...]
        module (str): Path to the module to test.
    
    Methods:
        retrieve_module_source: Returns source code of a module.
        retrieve_func_defs: Returns list of function names in Body.
        retrieve_class_defs: Returns list of class names in Body.
        retrieve_class_methods: Returns list of methods
            of a given class name.
        retrieve_func_source: Returns source code of a given function
            name.
        retrieve_class_source: Returns source code of a given class
            name.
        retrieve_classmethod_source: Returns source code of a given
            method name of a given class name.
        check_reqs_in_container: Checks if the container contains
            necessary requirements and libraries to run the tests.
        prepare_prompt: Prepare prompts [list of messages] for the API.
        postprocess_resp: Postprocess the test string returned by API.
    """
    def __init__(self, language: str, module: str):
        self.language = language
        self.module = module

    @abc.abstractmethod
    def retrieve_module_source(self) -> str:
        """Returns source code of a module."""
        pass

    @abc.abstractmethod
    def retrieve_func_defs(self) -> list:
        """Returns list of function names avaliable in Body."""
        pass
    
    @abc.abstractmethod
    def retrieve_class_defs(self) -> list:
        """Returns list of class names avaliable in Body."""
        pass
    
    @abc.abstractmethod
    def retrieve_class_methods(self, class_name: str) -> list:
        """Returns list of methods of a class given a class name."""
        pass

    @abc.abstractmethod
    def retrieve_func_source(self, func_name: str) -> str:
        """
        Returns source code of a func definiton given a func name."""
        pass
    
    @abc.abstractmethod
    def retrieve_class_source(self, class_name: str) -> str:
        """
        Returns source code of a class definition given a class name.
        """
        pass
    
    @abc.abstractmethod
    def retrieve_classmethod_source(
        self,
        class_name: str,
        method_name: str
    ) -> str:
        """
        Returns source code of a method definition given class 
        and method names.
        
        Args:
            class_name (str): Name of the class.
            method_name (str): Name of the method.
        """
        pass

    @abc.abstractmethod
    def check_reqs_in_container(self, container) -> Union[str, None]:
        """
        Checks if the container contains necessary requirements and
            libraries to run the tests.
        
        Args:
            container (docker.client.containers.Container): container.
        
        Returns:
            str: If there is a missing requirement, error message.
            None: If all requirements are fullfilled.
        """
        pass

    @abc.abstractmethod
    def prepare_prompt(
        self,
        obj_name: str,
        method_name: Union[str, None]=None
    ) -> list[dict[str, str]]:
        """
        Prepare prompts (list of messages) for the API call.

        Args:
            obj_name (str): Name of the object [class, func] to test.
            method_name (str): Name of the method to test if obj_name
                is a class. Defaults to None.

        Returns:
            list: containing system and initial user prompt.
                [
                    {'role': 'system', 'content': '...'},\n
                    {'role': 'user', 'content': '...'}
                ]
        Raises:
            ValueError: If obj_name or method_name not found.
        """
        pass

    @abc.abstractmethod
    def postprocess_resp(self, test: str, **kwargs) -> str:
        """
        Postprocesses the test string returned by the API.

        Args:
            test (str): The response string returned by the OpenAI API.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The postprocessed test string.
        """
        pass



