import openai
from . import language_adapters
# import tiktoken
from typing import Type
from .constants import MODELS, ADAPTERS
from .templates import COMPILING_ERROR_REPROMPT, TEST_ERROR_REPROMPT, list_errors

class TestGenerator:
    _api_key: str=None
    _org_key: str=None
    _model: str=None
    _adapter: Type[language_adapters.BaseAdapter]=None

    @classmethod
    def get_prompt(cls, obj_name: str, method=None) -> list:
        if cls._adapter is None:
            raise Exception("Adapter is not set. Please call the 'configure_adapter' method first.")
        messages = cls._adapter.prepare_prompt(obj_name, method)
        return messages

    @classmethod
    def _generate_tests(cls, messages: list, n_samples: int, temp: float) -> list[str]:
        response = openai.ChatCompletion.create(
            model=cls._model,
            messages=messages,
            temperature=temp,
            n=n_samples
        )
        responses_lst = [resp["message"]["content"] for resp in response["choices"]]
        return responses_lst
    
    @classmethod
    def generate_tests_pipeline(
        cls,
        initial_prompt: list[dict],
        n_samples: int=1,
        max_iter: int=5
    ) -> str:
        cls._check_authentication()
        cls._check_model()

        # Get initial prompt
        messages = initial_prompt

        # Generate First response: Linearly increase temperature based on number of tests slope: 0.05, max: 0.3
        # User setting
        temp = min(0.05 * (n_samples - 1), 0.3)
        responses = cls._generate_tests(messages, n_samples, temp)


        results: list[dict] = [dict() for _ in range(n_samples)]
        for i, resp in enumerate(responses):
            resp_str = resp
            for max_iter in range(max_iter):
                test_report = cls._adapter.run_tests_with_coverage(resp_str)
                if test_report["compile_error"]:
                    # If compiling code failed: reprompt
                    new_prompt = COMPILING_ERROR_REPROMPT.format(
                        error_msg=test_report["compile_error"],
                        language=cls._adapter.language
                    )
                    print(new_prompt)
                    messages.extend(
                        [
                            {'role': 'you', 'content': resp_str},
                            {'role': 'user', 'content': new_prompt}
                        ]
                    )
                    resp_str = cls._generate_tests(messages, 1, temp)[0]
                    print(resp_str)

                else:
                    # If compiling code succeeded:
                    if len(test_report["errors"]):
                        new_prompt = TEST_ERROR_REPROMPT.format(
                            id_error_str=list_errors(test_report["errors"]),
                            language=cls._adapter.language
                        )

                        # If errors occured
                        messages.extend(
                            [
                                {'role': 'you', 'content': resp_str},
                                {'role': 'user', 'content': new_prompt}
                            ]
                        )
                        resp_str = cls._generate_tests(messages, 1, temp)[0]
                    else:
                        # If no errors occured
                        results[i].update({"test": resp_str, "report": test_report})
                        break
        return results

    # @classmethod
    # def count_tokens(cls, string: str):
    #     """Returns the number of tokens in a text string."""
    #     tokenizer = tiktoken.encoding_for_model(cls._model)
    #     return  len(tokenizer(string))

    @classmethod
    def authenticate(cls, api_key: str, org_key: str=None) -> None:
        cls._api_key = api_key
        openai.api_key = api_key
        if org_key is not None:
            cls._org_key = org_key
            openai.organization = org_key
    
    @classmethod
    def set_model(cls, model: str="gpt-3.5-turbo") -> None:
        if model not in MODELS:
            raise ValueError(f"Supported Models: {MODELS}")
        """Defaults to gpt-3.5-turbo"""
        cls._model = model
    
    @classmethod
    def configure_adapter(cls, language: str, module: str) -> None:
        languages_aval = [*ADAPTERS.keys()]
        if language not in languages_aval:
            raise ValueError(f"Supported Programming Languages: {languages_aval}")
        cls._adapter = ADAPTERS[language](module)

    @classmethod
    def _check_authentication(cls) -> None:
        if cls._api_key is None:
            raise Exception("API not authenticated. Please call the 'authenticate' method first.")
    @classmethod
    def _check_model(cls) -> None:
        if cls._model is None:
            raise Exception("Please select a model endpoint calling 'set_model' method first.")
    
