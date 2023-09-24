#!/usr/bin/env python
"""
This script will be copied to '/app/autotestgen' directory
in the container and executed from there, in order to
avoid any malicious code execution in the local machine.

Parameters:
    - sys.argv[1]: Name of the language.
    - sys.argv[2]: Path to the module/script to test.

    
Important:
    - Every runner (function for running test for certain programming
        language) contained in runner_dict should return a
        dictionary containing:
        - 'tests_ran_n' (int): Number of tests that ran.
        - 'errors' (list[tuple(str, str)]): A list of tuples containing
            (test_id, traceback) for tests with errors.
        - 'failures' (list[tuple(str, str)]): A list of tuples
            containing (test_id, traceback) for tests with failures.
        - 'executed_lines' (list[int]): executed line numbers
            based on entire module/script.
        - 'missing_lines' (list[int]): missing line numbers
            based on entire module/script.
        - 'compile_error' (str): If there is a problem compiling
            the code provided by ChatGPT, this key is set to the
            error message.

"""
import sys, os, importlib.util, traceback
import tempfile, json
import unittest
import coverage
from typing import Union


def run_tests_with_coverage_python(module_dir: str) -> dict:
    """
    Run test code provided by GPT while measuring coverage.
    
    Parameters:
        module_dir (str): Path to the module/script to test.

    Important:
        - GPT generated code is already put in the container, under
            the filename 'test_source.py'.
    """
    
    def _run_tests() -> Union[unittest.TestResult, str]:
        """
        Runs the tests and returns the result.

        Returns:
            str: error message, if there is a problem compiling
                GPT generated code.
            unittest.TestResult: result of the tests.
        """
        try:
            spec = importlib.util.spec_from_file_location(
                name="test_source",
                location="/autotestgen/test_source.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except FileNotFoundError:
            raise
        except Exception as e:
            return traceback.format_exception_only(type(e), e)[-1]
    
        # Set-up Tests
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(module=module)
        runner = unittest.TextTestRunner(verbosity=2, warnings=False)
        # Run Tests
        result = runner.run(test_suite)
        return result

    # Unload module if already loaded to ensure correct cov tracking
    if module_dir.startswith("/"):
        mod_name = module_dir[1:-3].replace('/', '.')
    else:
        mod_name = module_dir[:-3].replace('/', '.')
    
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    # Create Temp file for json report
    try:
        temp_json = tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix=".json"
        )
    finally:
        temp_json.close()
        os.remove(temp_json.name)
    
    cov = coverage.Coverage(source=[mod_name], messages=True)
    cov.start()
    result = _run_tests()
    cov.stop()
    
    test_metadata = dict()
    if isinstance(result, str):
        test_metadata['compile_error'] = result
        return test_metadata
    
    try:
        cov.json_report(outfile=temp_json.name)
        with open(temp_json.name) as file:
            json_report = json.load(file)

        # Prepare metadata
        test_metadata['tests_ran_n'] = result.testsRun
        test_metadata['errors'] = [
            (str(n), err)
            for (n, err) in result.errors
        ]
        test_metadata["failures"] = [
            (str(n), err)
            for (n, err) in result.failures
        ]
        fn = [*json_report["files"].keys()][0]
        test_metadata['executed_lines'] = (
            json_report["files"][fn]['executed_lines']
        )
        test_metadata['missing_lines'] = (
            json_report["files"][fn]['missing_lines']
        )
        test_metadata['compile_error'] = None
    except:
        print("Error occured while writing coverage data in the container.")
    return test_metadata


# Dictionary of runners
runner_dict = {
    "python": run_tests_with_coverage_python
}

if __name__ == "__main__":
    # Path where local repo is mounted in container
    sys.path[0] = "/tmp/autotestgen/"
    # Run tests
    test_metadata = runner_dict[sys.argv[1]](sys.argv[2])
    with open("/autotestgen/test_metadata.json", "w") as f:
        json.dump(test_metadata, f)