
import abc
# Abstract Base Class

class BaseAdapter(abc.ABC):
    def __init__(self, language, testing_framework):
        self.framework = testing_framework
        self.language = language

    @abc.abstractmethod
    def retrieve_func_defs(self) -> list:
        """Returns list of function names avaliable for testing."""
        pass
    
    @abc.abstractmethod
    def retrieve_class_defs(self) -> list:
        """Returns list of class names avaliable for testing."""
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
    def _prepare_prompt_func(self, name: str)  -> list:
        """Helper Function for 'prepare_prompt' to generate Prompts for testing a Function definition."""
        pass
    
    @abc.abstractmethod
    def _prepare_prompt_class(self, name: str, method_name: str)  -> list:
        """Helper Function for 'prepare_prompt' to generate Prompts for testing a Class definition."""
        pass

    
    @abc.abstractmethod
    def run_tests_with_coverage(self):
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
        pass



