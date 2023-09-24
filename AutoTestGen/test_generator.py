import openai
import docker
from io import BytesIO
import tarfile, tempfile, json, os
from typing import Type
from . import language_adapters
from .constants import MODELS, ADAPTERS
from .templates import COMPILING_ERROR_REPROMPT, TEST_ERROR_REPROMPT, list_errors
from . import _run_tests_script

class TestGenerator:
    _api_key: str=None
    _org_key: str=None
    _model: str=None
    _container: docker.models.containers.Container=None
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
        obj_name: str=None,
        temp: float=0.1,
        n_samples: int=1,
        max_iter: int=5
    ) -> str:
        
        cls._check_authentication()
        cls._check_model()

        # Get initial prompt
        messages = initial_prompt
        # User setting
        responses = cls._generate_tests(messages, n_samples, temp)

        results: list[dict] = [dict() for _ in range(n_samples)]
        for i, resp in enumerate(responses):
            resp_str = cls._adapter.postprocess_response(resp, obj_name=obj_name)
            for iter in range(max_iter):
                test_report = cls.run_tests_in_container(resp_str)
                if test_report["compile_error"]:
                    # If compiling code failed: reprompt
                    new_prompt = COMPILING_ERROR_REPROMPT.format(
                        error_msg=test_report["compile_error"],
                        language=cls._adapter.language
                    )
                    messages.extend(
                        [
                            {'role': 'assistant', 'content': resp_str},
                            {'role': 'user', 'content': new_prompt}
                        ]
                    )
                    resp_str = cls._generate_tests(messages, 1, temp)[0]
                    print(f'Iteration {iter}:\n{resp_str}')
                
                elif test_report["errors"]:
                # If compiling code succeeded:
                    new_prompt = TEST_ERROR_REPROMPT.format(
                        id_error_str=list_errors(test_report["errors"]),
                        language=cls._adapter.language
                    )

                    # If errors occured
                    messages.extend(
                        [
                            {'role': 'assistant', 'content': resp_str},
                            {'role': 'user', 'content': new_prompt}
                        ]
                    )
                    resp_str = cls._generate_tests(messages, 1, temp)[0]
                else:
                    # If no errors occured
                    results[i].update({"messages": messages, "test": resp_str, "report": test_report})
                    break
        return results

    @classmethod
    def connect_to_container(cls, repo_dir:str, image: str="autotestgen:latest", cont_name: str="autotestgen") -> None:
        # check if image exists
        try:
            client = docker.from_env()
        except docker.errors.DockerException:
            print("Error while connecting to docker")
            raise
        
        if "autotestgen:latest" not in [img.tags[0] for img in client.images.list(all=True)]:
            raise Exception("autotestgen Image not found. Please build the image first.")
        
        if cont_name in [container.name for container in client.containers.list(all=True)]:
            if client.containers.get(cont_name).status == "running":
                client.containers.get(cont_name).stop()
            client.containers.get(cont_name).remove()
        try:
            # BIND REPO AS READ-ONLY
            cls._container = client.containers.create(
                image=image,
                name=cont_name,
                detach=True,
                tty=True,
                volumes={repo_dir: {'bind': '/tmp/autotestgen/', 'mode': 'ro'}}
            )
        except docker.errors.APIError:
            print("API Error occurred while creating container")
            raise
        except docker.errors.ImageNotFound:
            print("Image not found while creating container")
            raise
        except docker.errors.ContainerCreateError:
            print("Container creation failed")
            raise
        except Exception:
            print("An unexpected error occurred while creating container")
            raise
        finally:
            client.close()
        # start container
        cls._container.start()
        # Update status
        cls._container.reload()
        # Check if container is running
        if cls._container.status != "running":
            raise Exception("Container failed to start")
        # Move run_tests_script to container
        run_tests_file = _run_tests_script.__file__
        cls.put_file_to_container(run_tests_file, "/app/", arcname="run_tests.py")
    
    
    @classmethod
    def put_file_to_container(cls, dir_path: str, container_path: str, arcname: str) -> None:
        cls._check_container()
        stream = BytesIO()
        # write dir to stream
        with tarfile.open(fileobj=stream, mode="w:gz") as tar1:
            tar1.add(dir_path, arcname=arcname)
            
        # put stream to container
        try:
            cls._container.put_archive(
                path=container_path,
                data=stream.getvalue()
            )
        except docker.errors.APIError:
            print("API Error occured while moving file to container")
            raise
        except Exception:
            print("An unexpected error occurredw while moving file to container")
            raise
        finally:
                tar1.close()
                stream.close()
            
    @classmethod
    def get_file_content_from_container(cls, container_path: str) -> None:
        cls._check_container()
        try:
            data, _ = cls._container.get_archive(container_path)
        except docker.errors.APIError:
            print("API Error occured while getting file from container")
            raise
        except Exception:
            print("An unexpected error occurred while getting file from container")
            raise
        
        stream = BytesIO()
        # Write chunks in memory
        for chunk in data:
            stream.write(chunk)
        # Reset pointer to the beginning of the file
        stream.seek(0)
        tar = tarfile.open(mode="r", fileobj=stream)
        try:
            content = tar.extractfile(os.path.basename(container_path)).read().decode("utf-8")
        except:
            print("Error while extracting file from tar archive")
            raise
        finally:
            tar.close()
            stream.close()
        return content
    
    @classmethod
    def run_tests_in_container(cls, test_source: str) -> dict:
        # write test_source to tempfile and move to container
        cls._check_container()
        cls._check_adapter()
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=cls._adapter.suffix, delete=False) as temp_file:
                temp_file.write(test_source)
                temp_fn = temp_file.name
                temp_file.close()
                print(os.path.isfile(temp_fn))
                cls.put_file_to_container(temp_fn, "/app/", arcname=f"test_source{cls._adapter.suffix}")
        except Exception:
            print("An unexpected error occurred while writing to temp file")
            raise
        finally:
            temp_file.close()
            os.remove(temp_fn)
        # put file to container
        
        try:
            respond = cls._container.exec_run(
                f'python3 run_tests.py {cls._adapter.language} {cls._adapter.mod_name}')
        except:
            print("Running tests in container failed.")
            raise
        # get json report from container
        if 'json file successfully written.' in respond.output.decode("utf-8"):
            try:
                json_report = cls.get_file_content_from_container("/app/test_metadata.json")
            except:
                print("Getting json report from container failed.")
                raise
        else:
            raise Exception("Running tests in container failed.")
        report_dict = json.loads(json_report)
        return report_dict
    
    @classmethod
    def close_container(cls) -> None:
        cls._check_container()
        if cls._container.status == "running":
            cls._container.stop()
        cls._container.remove()
        cls._container = None

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
    def _check_container(cls) -> None:
        if cls._container is None:
            raise Exception("Container is not connected. Please call the 'connect_to_container' method first.")
    @classmethod
    def _check_adapter(cls) -> None:
        if cls._adapter is None:
            raise Exception("Adapter is not set. Please call the 'configure_adapter' method first.")
    @classmethod
    def _check_authentication(cls) -> None:
        if cls._api_key is None:
            raise Exception("API not authenticated. Please call the 'authenticate' method first.")
    @classmethod
    def _check_model(cls) -> None:
        if cls._model is None:
            raise Exception("Please select a model endpoint calling 'set_model' method first.")
    
    
