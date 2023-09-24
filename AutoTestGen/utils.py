from . import config
from .constants import MODELS, ADAPTERS
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
