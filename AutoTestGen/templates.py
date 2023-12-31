from typing import Union
INITIAL_SYSTEM_PROMPT: str = (
    "Generate high-quality comprehensive unit tests in {language} "
    "using {framework} library for provided {obj_desc}.\n"
    "Next to the definition you will be provided with numbered INFO sheet "
    "that might be useful in generating finer tests.\n"
    "You do not necessarily need to use all of the INFO sheet, use only "
    "relevant parts of it.\nYour response should be just a valid {language} "
    "code without explanation or any other text.\n"
)

INITIAL_USER_PROMPT: str = (
    "{object_type} Definition:\n{source_code}\n\nINFO sheet:\n{info_sheet}"
)

COMPILING_ERROR_REPROMPT: str = (
    "The code that you have provided failed to compile with the following "
    "error:\n{error_msg}\nTry to fix the error and resubmit your response.\n"
    "Your response should still be just a valid {language} code without "
    "explanation or any other text."
)

TEST_ERROR_REPROMPT: str = (
    "While running the tests following errors occured:\n{id_error_str}"
    "Try to fix them and resubmit your response.\nYour response should still "
    "be just a valid {language} code without explanation or any other text."
)

COMBINING_SAMPLES_PROMPT: str = (
    "For the following prompt:\n{initial_prompt}\nYou have generated "
    "following {n_samples} responses, which have resulted in the subsequent "
    "outcomes:\n{combined_samples}\nConsidering all the provided responses "
    "and their corresponding outcomes, generate a single best response. "
    "Your response should still be just a valid {language} code without "
    "explanation or any other text."
)

# Helper functions
def list_errors(errors: list[tuple[str, str]]) -> str:
    """
    Returns a string containing test_name-error_msg pairs.
    
    Args:
        errors: list of tuples containing test_name and error_msg.
    """
    error_str = "\n".join(
        [
            f"{i}. Test {test_id} failed with error: {error_msg}"
            for i, (test_id, error_msg) in enumerate(errors, start=1)    
        ]
    )
    return error_str

def combine_samples(samples: list[tuple]) -> str:
    """
    Returns a string containing response-test_result pairs.

    Args:
        samples: list of tuples containing response and test_result.
    """
    combined_str = "\n".join(
        [
            f"{i}. Response:\n{resp}\nResult: {result}"
            for i, (resp, result) in enumerate(samples, start=1)    
        ]
    )
    return combined_str

def generate_python_info_sheet(
    object_type: str,
    module_name: str,
    imports: str,
    constants: str, 
    variables: str,
    local_type_variables: str,
    local_call_defs: str,
    class_name: Union[str, None]=None,
    init: Union[str, None]=None,
    class_attributes: Union[str, None]=None,
) -> str:
    """
    Retunrs a string containing info about the module and the object 
    to test.

    Args:
        obj_type (str): one of ['class', 'function'].
        module_name (str): name of the module object is defined in.
        imports (str): string containing imports made in the module.
        constants (str): string containing imported constants.
        variables (str): string containing variables defined 
            in the module body.
        local_call_defs (str): string containing relevant definitions
            of functions and methods used inside the object body.
    
    Class specific:
        class_name (str): name of the class method is defined in.
        init (str): definition of the __init__ method of the class.
        class_attributes (str): string containing class attributes.
    """
    assert object_type in ["method", "function"]
    
    n = 2
    # Intro Points
    if object_type == "method":
        info_sheet = (
            f"1. {class_name} class is defined in the module called: "
            f"{module_name}\n"
        )
        if init:
            info_sheet += (
                f"2. Class __init__ definition of {class_name}:\n{init}\n"
            )
            n += 1
        if class_attributes:
            info_sheet += f"3. {class_name} attributes:{class_attributes}\n"
            n += 1
    elif object_type == "function":
        info_sheet = (
            f"1. Function is defined in the module called: {module_name}\n"
        )
    
    # Further Points
    if imports:
        info_sheet += (
            f"{n}. Following imports were made inside the {module_name} "
            f"module:\n{imports}\n"
        )
        n += 1

    if constants:
        info_sheet += (
            f"{n}. Following constants were imported in the {module_name} "
            f"module:\n{constants}\n"
        )
        n += 1
    
    if variables:
        info_sheet += (
            f"{n}. Following variables were decleared in the {module_name} "
            f"module body:\n{variables}\n"
        )
        n += 1

    if local_type_variables != "":
        info_sheet += (
            f"{n}. Additionally variable types for body-decleared variables"
            f"whose types are not obvious:\n{local_type_variables}\n"
        )
        n += 1
    
    if local_call_defs != "":
        info_sheet += (
            f"{n}. Definitons of functions used inside the definition "
            f"body:\n{local_call_defs}"
        )

    return info_sheet

