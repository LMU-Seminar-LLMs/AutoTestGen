#!/usr/bin/env python

"""
This script will be copied to the container (after connecting to container )and run there to avoid any mallicious code execution on the local machine.
The code provided by ChatGPT is as well copied to the container as a 'test_source.{suffix}' file.
Both are stored in the '/app/' directory of the container.
"""
import tempfile
import sys
import coverage
import importlib.util
import traceback
import os
import unittest
import json

def run_tests_with_coverage_python(mod_name: str):
    """
        This function runs tests genereated by ChatGPT and returns the result. It only takes name of the module/script to test as an argument.

        Parameters:
            mod_name (str): Name of the module or script to test.

        Returns:
            dict: A dictionary containing specific key-value pairs.\n
            - 'tests_ran_n' (int): Number of tests that ran.\n
            - 'errors' (list[tuple(str, str)]): A list of tuples containing (test_id, traceback_message)
                        for tests with errors.\n
            - 'failures' (list[tuple(str, str)]): A list of tuples containing (test_id, traceback_message)
                        for tests with failures.\n
            - 'executed_lines' (list[int]): executed line numbers [based on the entire module or script].\n
            - 'missing_lines' (list[int]): missing line numbers [based on the entire module or script].
            - 'compile_error' (str): If there is a problem compiling the code provided by ChatGPT,
                            this is set to the error message.

        Exception:
            If there is a problem compiling the code provided by ChatGPT, dict['compail_fail'] is set to the error message.
    """
    def _run_tests():
        """Runs the tests and returns the result."""
        try:
            # Try Loading Temp file as module: Checks if provided code by ChatGPT is a valid module/script
            # test_source file is already put in the container
            spec = importlib.util.spec_from_file_location("test_source", "test_source.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            return traceback.format_exception_only(type(e), e)[-1]
        # Set-up Tests
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(module=module)
        runner = unittest.TextTestRunner(verbosity=2, warnings=False)
        # Run Tests
        result = runner.run(test_suite)
        return result

    if mod_name in sys.modules:
        del sys.modules[mod_name]

    # Create Temp file for json report
    try:
        temp_json = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json")
    finally:
        temp_json.close()
    
    cov = coverage.Coverage(source=[mod_name], messages=True)
    cov.start()
    result = _run_tests()
    cov.stop()
    
    test_metadata = dict()
    if isinstance(result, str):
        # Return exception message
        test_metadata['compile_error'] = result
        return test_metadata
    try:
        cov.json_report(outfile=temp_json.name)
        with open(temp_json.name) as file:
            json_report = json.load(file)
        temp_json.close()
        os.remove(temp_json.name)

        # Prepare metadata
        test_metadata['tests_ran_n'] = result.testsRun
        test_metadata['errors'] = result.errors
        test_metadata["failures"] = result.failures
        fn = [*json_report["files"].keys()][0]
        test_metadata['executed_lines'] = json_report["files"][fn]['executed_lines']
        test_metadata['missing_lines'] = json_report["files"][fn]['missing_lines']
        test_metadata['compile_error'] = None
    except:
        test_metadata['compile_error'] = f"Make sure to import the definition from {mod_name} module. "\
            f"Include 'from {mod_name} import *' in your response."
    return test_metadata


runner_dict = {
    "python": run_tests_with_coverage_python
}

if __name__ == "__main__":
    sys.path[0] = "/tmp/autotestgen/"
    test_metadata = runner_dict[sys.argv[1]](sys.argv[2])
    # Write metadata to json
    with open("test_metadata.json", "w") as f:
        json.dump(test_metadata, f)
    print("json file successfully written.")

