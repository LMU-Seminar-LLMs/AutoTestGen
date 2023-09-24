
import abc
# Abstract Base Class

class BaseAdapter(abc.ABC):
    def __init__(self, language, testing_framework):
        self.framework = testing_framework
        self.language = language

    @abc.abstractmethod
    def prepare_prompt(self, name:str, method_name=None):
        pass
    
    @abc.abstractmethod
    def _prepare_prompt_func(self, name:str):
        pass
    
    @abc.abstractmethod
    def _prepare_prompt_class(self, name: str, method_name):
        pass

    @abc.abstractmethod
    def compute_coverage():
        pass