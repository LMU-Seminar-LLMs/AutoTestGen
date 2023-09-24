import abc
from typing import Union

class BaseAdapter(abc.ABC):
    def __init__(self, language, testing_framework):
        self.framework = testing_framework
        self.language = language


    @classmethod
    @property
    @abc.abstractmethod
    def suffix(cls) -> str:
        """Enforces that all subclasses of the BaseAdapter class have a suffix attribute."""
        pass

    @abc.abstractmethod
    def retrieve_module_source(self) -> str:
        """Returns source code of a module"""
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
        """Returns list of methods of a class given a class name"""
        pass

    @abc.abstractmethod
    def retrieve_func_source(self, func_name: str) -> str:
        """Returns source code of a function definiton given a function name"""
        pass
    
    @abc.abstractmethod
    def retrieve_class_source(self, func_name: str):
        """Returns source code of a class definition given a class name"""
        pass
    
    @abc.abstractmethod
    def retrieve_classmethod_source(self, class_name: str, method_name: str):
        """Returns source code of a method definition given a class name and method name"""
        pass

    @abc.abstractmethod
    def check_requirements_in_container(self, container) -> Union[str, None]:
        """Checks if the container contains necessary requirements and libraries to run the tests."""
        pass

    @abc.abstractmethod
    def prepare_prompt(self, name: str, method_name: str=None) -> list:
        """
        Prepare prompts (list of messages) for the API.

        Parameters:
            obj_name (list): Name of an object (class- or function- definition) to test.
        Returns:
            list: containing messages for API.
        Raises:
            ValueError: If the provided obj_name or method_name cannot be found in given module or script.
        """
        pass
    @abc.abstractmethod
    def postprocess_response(self, test: str, **kwargs) -> str:
        """
        Postprocesses the test string returned by the API.

        Parameters:
            test (str): The response string returned by the OpenAI API.

        Returns:
            str: The postprocessed test string.
        """
        pass



