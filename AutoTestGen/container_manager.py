
import docker
from io import BytesIO
import tarfile, os, tempfile, json, re
from . import _run_tests_script, config
from .constants import SUFFIXES

class ContainerManager:
    """
    Class for managing the docker container.
    
    Attributes:
        repo_dir (str): Path to the selected repo.
        image_name (str): Name of the docker image to use. [Name:Tag]
        client (docker.client.DockerClient): Docker client connection.

    Constants:
        container_name (str) = "autotestgen"

    Importand Methods:
        start_container: Starts a docker container and mounts the
            repo_dir as read-only.
        validate_image_name: Validates wether image exists in docker
            environment or not.
        validate_container_requirements: Checks if the container has
            the required python version.
        put_file_to_container: Puts a file to the container.
        get_file_from_container: Gets a file from the container.
        run_tests_in_container: Runs the tests in the container.

    """
    def __init__(self, image_name: str, repo_dir: str):
        """
        Important:
            - Creates a container with the specified image.
            - Starts the container.
            - Checks if the container has the required python version.
            - Copies the run_tests_script to the container.
        """
        self.repo_dir = repo_dir
        self.container_name = "autotestgen"
        self.client = self.connect_to_docker_client()
        
        _ = self.validate_image_name(image_name)
        self.image_name = image_name
        self.container = self.start_container()
        _ = self.validate_container_requirements()

        self.container.exec_run("mkdir -p /autotestgen/")
        # Copy the run_tests_script to the container
        run_tests_script = _run_tests_script.__file__
        _ = self.put_file_to_container(
            run_tests_script,
            "/autotestgen/",
            arcname="run_tests.py"
        )

    def validate_image_name(self, image_name: str) -> None:
        """
        Validates wether image exists in docker env or not.

        Args:
            image_name (str): Name of the docker image. [Name:Tag]
        
        Raises:
            ValueError: If the image is not found.
        """
        images = self.list_avaliable_images()
        if image_name not in images:
            raise ValueError(
                f"Specified image not found. Avaliable images:\n{images}"
            )
    
    def validate_container_requirements(self) -> None:
        """
        Checks if the container has the required python version.
        
        Raises:
            RuntimeError: If python not installed or version is < 3.9.
            in the container.
        """
        resp = self.container.exec_run("python3 --version")
        if resp.exit_code != 0:
            raise RuntimeError("Error occured while checking python version.")
        vers = resp.output.decode("utf-8")
        major, minor = re.search(r"(\d+\.\d+)", vers).group(1).split(".")
        if int(major) < 3 or int(minor) < 9:
            raise RuntimeError(
                "Python version in the container must be >= 3.9."
            )
    
    def connect_to_docker_client(self) -> docker.client.DockerClient:
        """
        Connects to the docker client.
        
        Returns:
            docker.client.DockerClient: Docker client connection.
        """
        client = docker.from_env()
        return client

    def list_avaliable_images(self) -> list[str]:
        """
        List all the available docker images.
        
        Returns:
            list[str]: List of in env available docker images.
        """
        return [image.tags[0] for image in self.client.images.list(all=True)]

    def get_container_status(self) -> str:
        """Returns the status of the container."""
        try:
            container = self.client.containers.get(self.container_name)
        except docker.errors.NotFound:
            return "Container not found."
        return container.status

    def start_container(self):
        """
        Starts a docker container and mounts the repo_dir as read-only.
        
        Raises:
            RuntimeError: If container fails to start.
        
        Returns:
            docker.client.containers.Container: Container object.

        """
        # If container already exists remove it.
        conts = [c.name for c in self.client.containers.list(all=True)]
        if self.container_name in conts:
            if self.get_container_status() == "running":
                self.client.containers.get(self.container_name).stop()
            self.client.containers.get(self.container_name).remove()
        
        # Start container + mount the repo_dir as read-only.
        volumes = {self.repo_dir: {'bind': '/tmp/autotestgen/', 'mode': 'ro'}}
        container = self.client.containers.create(
            image=self.image_name,
            name=self.container_name,
            detach=True,
            tty=True,
            volumes=volumes
        )
        container.start()
        # Update status
        container.reload()
        if self.get_container_status() != "running":
            raise RuntimeError("Container failed to start.")
        return container
        
    def put_file_to_container(
        self,
        dir_path: str,
        dir_in_container: str,
        arcname: str
    ) -> None:
        """
        Puts a file to the container.

        Args:
            dir_path (str): Path to the directory containing the file.
            dir_in_container (str): Destination dir in the container.
            arcname (str): Filename to use in the container.

        Important:
            Creates a tarfile in memory and sends it to the container
            via BytesIO.
        """

        stream = BytesIO()
        try:
            with tarfile.open(fileobj=stream, mode='w:gz') as tar:
                tar.add(dir_path, arcname=arcname)
        except:
            print("Error occured while creating tarfile.")
            raise
        finally:
            tar.close()

        try:
            self.container.put_archive(
                path=dir_in_container,
                data=stream.getvalue()
            )
        except:
            print("Error occured while putting the file to container.")
            raise
        finally:
            stream.close()

    def get_file_from_container(self, path_in_container: str) -> str:
        """
        Gets a file from the container.
        
        Args:
            path_in_container (str): Path to the file in the container.
        
        Important:
            Creates a tarfile in memory and writes contents from the
            file located in container via BytesIO.

        Returns:
            str: Content of the file.
        """
        
        try:
            data, _ = self.container.get_archive(path_in_container)
        except docker.errors.APIError:
            print("API error while getting the file from container.")
            raise
        except Exception as e:
            print("Unexpected error while getting the file from container.")
            raise
        
        stream = BytesIO()
        for chuck in data:
            stream.write(chuck)
        stream.seek(0)
        try:
            tar = tarfile.open(fileobj=stream, mode='r')
            content = tar.extractfile(
                os.path.basename(path_in_container)
            ).read().decode("utf-8")
        except:
            print("Error occured while extracting the file.")
            raise
        finally:
            stream.close()
            tar.close()
        
        return content

    def run_tests_in_container(self, test_source: str) -> dict:
        """
        Runs the tests in the container.

        Args:
            test_source (str): Source code of the test.

        Returns:
            dict: Dictionary containing the test results and coverage
                data. Check the _run_tests_script.py for the structure
                of the dict.

        Raises:
            ValueError: If ADAPTER is not set.
            RuntimeError: If running tests in container fails.
        """
        if config.ADAPTER is None:
            raise ValueError("ADAPTER is not set. Call set_app_config first.")
        suffix = SUFFIXES[config.ADAPTER.language]
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=suffix,
                delete=False
            ) as temp_file:
                temp_file.write(test_source)
                temp_fn = temp_file.name
                temp_file.close()
            _ = self.put_file_to_container(
                temp_fn,
                "/autotestgen/",
                arcname="test_source"+suffix
            )
        except:
            print("Error occured while creating temp file.")
            raise
        finally:
            os.remove(temp_fn)

        language = config.ADAPTER.language
        module_dir = config.ADAPTER.module
        cmd = f"python3 /autotestgen/run_tests.py {language} {module_dir}"
        try:
            resp = self.container.exec_run(cmd)
        except:
            print(
                "Error while executed following cmd inside container:\n" + cmd
            )
            raise

        if resp.exit_code != 0:
            raise RuntimeError(
                (
                    "Running tests in container failed with following error: "
                    + resp.output.decode("utf-8")
                )
            )
        
        json_report = self.get_file_from_container(
            "/autotestgen/test_metadata.json"
        )
        report_dict = json.loads(json_report)
        return report_dict

    def close_container(self) -> None:
        """Stops and removes the container."""
        if self.get_container_status() == "running":
            self.container.stop()
        self.container.remove()

    def __del__(self) -> None:
        self.client.close()