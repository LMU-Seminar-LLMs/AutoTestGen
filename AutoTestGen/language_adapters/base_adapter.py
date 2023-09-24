import abc
from typing import Union

class BaseAdapter(abc.ABC):
    def __init__(self, language: str, testing_framework: str, mod_name: str):
        self.framework = testing_framework
        self.language = language
        self.mod_name = mod_name 

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
        Returns source code of a method def given class, method names.
        
        Parameters:
            class_name (str): Name of the class.
            method_name (str): Name of the method.
        """
        pass

    @abc.abstractmethod
    def check_reqs_in_container(self, container) -> Union[str, None]:
        """
        Checks if the container contains
            necessary requirements and libraries to run the tests.
        
        Parameters:
            container (docker.client.containers.Container): container.
        
        Returns:
            str: If there is a problem with the requirements, 
                returns the error message as string.
            None: If there is no problem with the requirements.
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

        Parameters:
            obj_name (str): Name of the object (class, func) to test.
            method_name (str): Name of the method to test if obj_name 
                is a class.

        Returns:
            list: containing messages and corresponding roles for API.
        
        Raises:
            ValueError: If the provided obj_name or method_name
                cannot be found in given module or script.
        """
        pass
    @abc.abstractmethod
    def postprocess_resp(self, test: str, **kwargs) -> str:
        """
        Postprocesses the test string returned by the API.

        Parameters:
            test (str): The response string returned by the OpenAI API.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The postprocessed test string.
        """
        pass



