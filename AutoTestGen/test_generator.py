import openai
from . import language_adapters
import tiktoken
from typing import Type, TYPE_CHECKING

adapter_registry = {
    "python": language_adapters.PythonAdapter,
    "java": language_adapters.JavaAdapter,
    "r": language_adapters.RAdapter
}


class TestGenerator:
    _api_key: str
    _org_key: str
    _model: str
    _tokenizer: tiktoken.core.Encoding
    _adapter: Type[language_adapters.BaseAdapter]

    @classmethod
    def get_prompt(cls, obj_name, method=None):
        if cls._adapter is None:
            raise Exception("Adapter is not set. Please call the 'configure_adapter' method first.")
        messages = cls._adapter.prepare_prompt(obj_name, method)
        return messages

    @classmethod
    def generate_tests(cls, messages: list):
        cls._check_authentication()
        cls._check_model()
        response = openai.ChatCompletion.create(
            model=cls._model,
            messages=messages,
            temperature=0
        )
        return response.choices[0].message["content"]
    
    @classmethod
    def count_tokens(cls, string):
        """Returns the number of tokens in a text string."""
        return  len(cls._tokenizer(string))
    

    @classmethod
    def authenticate(cls, api_key:str, org_key=None) -> None:
        cls._api_key = api_key
        openai.api_key = api_key
        if org_key is not None:
            cls._org_key = org_key
            openai.organization = org_key
    
    @classmethod
    def set_model(cls, model: str="gpt-3.5-turbo") -> None:
        """Defaults to gpt-3.5-turbo"""
        cls._model = model
        cls._tokenizer = tiktoken.encoding_for_model(cls._model)
    
    @classmethod
    def configure_adapter(cls, language, module):
        languages_aval = [*adapter_registry.keys()]
        if language not in languages_aval:
            raise ValueError(f"Supported Programming Languages: {languages_aval}")
        cls._adapter = adapter_registry[language](module)

    @classmethod
    def _check_authentication(cls):
        if cls._api_key is None:
            raise Exception("API not authenticated. Please call the 'authenticate' method first.")
    @classmethod
    def _check_model(cls):
        if cls._model is None:
            raise Exception("Please select a model endpoint calling 'set_model' method first.")
        

    