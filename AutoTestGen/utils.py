from . import config
from .constants import MODELS, ADAPTERS
from typing import Union
import tiktoken

def set_api_keys(api_key: str, org_key: str) -> None:
    """
    Set the API key, organization key for OpenAI API.

    Args:
        api_key (str): OpenAI API key.
        org_key (str): OpenAI organization key.
    """   
    config.API_KEY = api_key
    config.ORG_KEY = org_key

def set_model(model: str) -> None:
    """
    Set the model to use for OpenAI API.

    Args:
        model (str): Model checkpoint to use.
    
    Raises:
        ValueError: If the model is not supported.
    """
    if model not in MODELS:
        raise ValueError(f"Model {model} is not supported.")
    config.MODEL = model

def set_adapter(language: str, module_dir: str) -> None:
    """
    Set the programming language adapter to use.

    Args:
        language (str): Programming Language name.
        module_dir (str): Directory to the module to test.
    
    Raises:
        ValueError: If the language is not supported.
    """
    if language not in ADAPTERS:
        raise ValueError(f"Language {language} is not supported.")
    config.ADAPTER = ADAPTERS[language](module=module_dir)


def count_tokens(messages: list[dict[str, str]]) -> int:
    """
    Counts number of tokens in list of prompts.

    Args:
        messages (list): List of dicts containing role-content keys.

    Returns:
        int: Number of tokens in the list of prompts.
    """
    encoding = tiktoken.encoding_for_model(config.MODEL)
    num_tokens = [len(encoding.encode(m["content"])) for m in messages]
    return sum(num_tokens)


def find_lines(
    obj: str,
    obj_type: str,
    class_name: Union[str, None]=None
) -> tuple[int, int, list[str]]:
    """
    Finds start, end lines of obj definition in module source code.

    Args:
        obj: name of the object.
        obj_type: One of ["function", "class", "class method"].
        class_name: class name if obj_type is class method.

    Returns:
        tuple of position where source_code starts, ends and source
            code line by line in a list.

    """
    if config.ADAPTER is None:
        raise ValueError("Adapter is not set.")
    module_source: str = config.ADAPTER.retrieve_module_source()
    obj_source = _retrieve_source(obj, obj_type, class_name)

    target_lines = [line.strip() for line in obj_source.split("\n")]
    lines = [line.strip() for line in module_source.split("\n")]
    
    for index, _ in enumerate(lines):
        if (
            lines[index] == target_lines[0] and 
            lines[index: index + len(target_lines)] == target_lines
        ):
            start_line = index + 1
            end_line = index + len(target_lines)
            break
    return start_line, end_line, obj_source.split("\n")

def _retrieve_source(
    obj: str,
    obj_type: str,
    class_name: Union[str, None]=None
) -> str:
    """Helper function for find_lines."""
    if obj_type == "function":
        return config.ADAPTER.retrieve_func_source(obj)
    elif obj_type == "class":
        return config.ADAPTER.retrieve_class_source(obj)
    elif obj_type == "class method":
        return config.ADAPTER.retrieve_classmethod_source(
            class_name,
            method_name=obj
        )
    else:
        raise ValueError(
            "obj_type must be one of ['function', 'class', 'class method']"
        )
