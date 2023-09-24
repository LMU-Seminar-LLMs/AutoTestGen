from . import config
from .constants import MODELS, ADAPTERS
from typing import Union
import tiktoken

def set_api_keys(
    api_key: Union[str, None],
    org_key: Union[str, None]
) -> None:
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


def compute_coverage(
    object_name: str,
    object_type: str,
    test_metadata: list[dict],
    class_name: Union[str, None]=None
) -> int:
    """
    Computes accumulated coverage for a list of tests of the same object.
    
    Args:
        object_name: Name of the object.
        object_type: One of ['function', 'class', 'class method'].
        test_metadata: list of dicts containing test metadata.
            every dict contains keys: "executed_lines", "missing_lines".
        class_name: Name of the class if object_type is class method.
    
    Returns:
        int between 0 and 100.
    """
    if not test_metadata:
        return 0
    executed, missing = collect_executed_missing_lines(
        object_name, object_type, test_metadata, class_name
    )
    return int(len(executed) / (len(executed) + len(missing)) * 100)


def collect_executed_missing_lines(
    object_name: str,
    object_type: str,
    test_metadata: list[dict],
    class_name: Union[str, None]=None
) -> tuple[set[int], set[int]]:
    """
    Collects executed, missing lines over all available tests in a set.
    Helper function for compute_coverage.
    """
    # Find start, end lines of the object definition
    st, end, _ = find_lines(object_name, object_type, class_name)
    # Collect executed, missing lines over all available tests in a set
    exec_lines = [test["executed_lines"] for test in test_metadata]
    miss_lines = [test["missing_lines"] for test in test_metadata]
    execs = {it for subl in exec_lines for it in subl if st <= it <= end}
    miss = {it for subl in miss_lines for it in subl if st <= it <= end}
    miss = miss.difference(execs)
    return execs, miss


def find_lines(
    object_name: str,
    object_type: str,
    class_name: Union[str, None]=None
) -> tuple[int, int, list[str]]:
    """
    Finds start, end lines of the object definition in module source code.

    Args:
        object_name: name of the object.
        object_type: One of ["function", "class", "class method"].
        class_name: class name if object_type is class method.

    Returns:
        tuple of position where source_code starts, ends and source
            code line by line in a list.

    Raises:
        ValueError: If the adapter is not set.
        ValueError: If the object type is not supported.
    """
    if config.ADAPTER is None:
        raise ValueError("Adapter is not set.")
    module_source: str = config.ADAPTER.retrieve_module_source()
    obj_source = _retrieve_source(object_name, object_type, class_name)

    target_lines = [line.strip() for line in obj_source.split("\n")]
    lines = [line.strip() for line in module_source.split("\n")]
    
    for index, _ in enumerate(lines):
        if (
            lines[index] == target_lines[0] and 
            lines[index: index + len(target_lines)] == target_lines
        ):
            start_line = index + 1
            end_line = start_line + len(target_lines) - 1
            break
    return start_line, end_line, obj_source.split("\n")

def _retrieve_source(
    object_name: str,
    object_type: str,
    class_name: Union[str, None]=None
) -> str:
    """
    Retrieves source code of the object using the adapter instance.
    Helper function for find_lines.
    """
    if object_type == "function":
        return config.ADAPTER.retrieve_func_source(object_name)
    elif object_type == "class":
        return config.ADAPTER.retrieve_class_source(object_name)
    elif object_type == "class method":
        return config.ADAPTER.retrieve_classmethod_source(
            class_name,
            method_name=object_name
        )
    else:
        raise ValueError(
            "object_type must be one of ['function', 'class', 'class method']"
        )
