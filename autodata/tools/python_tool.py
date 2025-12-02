"""Core helpers for executing Python code within AutoData.

Example:
    >>> from pathlib import Path
    >>> from autodata.tools.python_tool import DockerPythonExecutor
    >>> executor = DockerPythonExecutor(Path(\"/tmp/autodata-work\"))  # doctest: +SKIP
    >>> result = executor.execute(\"print('hello from docker')\")  # doctest: +SKIP
    >>> result.stdout  # doctest: +SKIP
    'hello from docker\\n'
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import docker
import structlog
from docker.client import DockerClient
from docker.errors import APIError, DockerException, ImageNotFound
from requests import exceptions as requests_exceptions

from autodata.configs.api_registry import iter_api_metadata
from autodata.configs.helper import load_environment_variables_from_file

DEFAULT_IMAGE = "jupyter/scipy-notebook:latest"
logger = structlog.get_logger(__name__)


@dataclass
class PythonExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def to_legacy_payload(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "success": self.success,
        }


@dataclass(slots=True)
class DockerExecutionContext:
    """Container execution context assembled prior to launching Docker."""

    script: Path
    requirements: Path | None
    command: list[str]
    volumes: dict[str, dict[str, str]]
    environment: dict[str, str]
    metadata: dict[str, Any]

    def cleanup(self) -> None:
        """Remove temporary files created for Docker execution."""

        self.script.unlink(missing_ok=True)
        if self.requirements:
            Path(self.requirements).unlink(missing_ok=True)


class PythonExecutor:
    def __init__(self, work_dir: str | Path) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, code: str, *, timeout: int = 300) -> PythonExecutionResult:
        script = self._prepare_script(code)
        try:
            proc = subprocess.run(
                ["python", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.work_dir,
            )
            return PythonExecutionResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
            )
        finally:
            script.unlink(missing_ok=True)

    def _prepare_script(self, code: str) -> Path:
        script = self.work_dir / generate_validation_filename()
        script.write_text(code)
        return script


class DockerPythonExecutor(PythonExecutor):
    """Execute Python code inside isolated Docker containers.

    The executor mounts the configured work directory into each container,
    installs optional dependencies from ``requirements.txt``, forwards API
    credentials sourced from :data:`autodata.configs.api_registry.API_INFO`, and captures
    structured metadata (including container identifiers and execution timing).
    Containers are removed after execution, even when exceptions are raised.
    """

    def __init__(self, work_dir: str | Path, *, image: str = DEFAULT_IMAGE) -> None:
        super().__init__(work_dir)
        self.image = image
        self._client = _get_docker_client()

    def _create_execution_context(
        self,
        code: str,
        dependencies: Sequence[str] | None,
    ) -> DockerExecutionContext:
        metadata: dict[str, Any] = {
            "image": self.image,
            "dependencies": sorted(set(dependencies or [])),
        }

        environment = _load_api_credentials()
        if environment:
            metadata["environment_keys"] = sorted(environment.keys())

        requirements: Path | None = None
        if dependencies:
            requirements = create_requirements_file(dependencies, self.work_dir)

        script = self._prepare_script(code)
        metadata["script_name"] = script.name
        if requirements:
            metadata["requirements_file"] = str(requirements)

        workspace_path = Path(self.work_dir).resolve()
        volumes: dict[str, dict[str, str]] = {
            str(workspace_path): {
                "bind": "/workspace",
                "mode": "rw",
            }
        }

        command: list[str] = ["python", f"/workspace/{script.name}"]
        if requirements:
            requirements_path = Path(requirements).resolve()
            volumes[str(requirements_path)] = {
                "bind": "/tmp/requirements.txt",
                "mode": "ro",
            }
            install_and_run = (
                "pip install -q -r /tmp/requirements.txt && "
                f"python /workspace/{script.name}"
            )
            command = ["/bin/bash", "-c", install_and_run]

        return DockerExecutionContext(
            script=script,
            requirements=requirements,
            command=command,
            volumes=volumes,
            environment=environment,
            metadata=metadata,
        )

    @staticmethod
    def _collect_container_logs(container: docker.models.containers.Container) -> tuple[str, str]:
        stdout_bytes = container.logs(stdout=True, stderr=False) or b""
        stderr_bytes = container.logs(stdout=False, stderr=True) or b""
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        return stdout_text, stderr_text

    def _ensure_image_available(self) -> None:
        try:
            _pull_image_with_retry(self._client, self.image)
        except ImageNotFound as exc:
            message = (
                f"Docker image '{self.image}' could not be found. "
                "Ensure the image exists or is accessible."
            )
            raise ImageNotFound(
                message,
                response=getattr(exc, "response", None),
                explanation=getattr(exc, "explanation", None),
            ) from exc

    def execute(
        self,
        code: str,
        *,
        timeout: int = 300,
        dependencies: Sequence[str] | None = None,
    ) -> PythonExecutionResult:
        if not code or not code.strip():
            raise ValueError("Python code must be a non-empty string.")
        context = self._create_execution_context(code, dependencies)
        metadata = context.metadata
        container = None
        stdout_text = ""
        stderr_text = ""
        exit_code = 1
        start_time = time.monotonic()
        duration: float | None = None

        try:
            self._ensure_image_available()

            container = self._client.containers.run(
                image=self.image,
                command=context.command,
                volumes=context.volumes,
                working_dir="/workspace",
                environment=context.environment or None,
                detach=True,
                stdout=True,
                stderr=True,
                remove=False,
            )
            metadata["container_id"] = container.id
            short_id = _short_container_id(container.id)
            logger.info(
                "Docker container started.",
                image=self.image,
                container_id=short_id,
            )

            wait_result = container.wait(timeout=timeout)
            exit_code = wait_result.get("StatusCode", exit_code)
            stdout_text, stderr_text = self._collect_container_logs(container)
            duration = time.monotonic() - start_time
            logger.info(
                "Docker container completed.",
                image=self.image,
                container_id=short_id,
                exit_code=exit_code,
                duration_seconds=duration,
            )
        except requests_exceptions.ReadTimeout as exc:
            short_id = _short_container_id(
                metadata.get("container_id") or getattr(container, "id", None)
            )
            logger.error(
                "Docker container execution timed out.",
                image=self.image,
                container_id=short_id,
                timeout_seconds=timeout,
            )
            if container is not None:
                try:
                    container.kill()
                except DockerException as kill_exc:  # pragma: no cover - defensive
                    logger.warning(
                        "Failed to kill timed-out Docker container.",
                        image=self.image,
                        container_id=short_id,
                        error=str(kill_exc),
                    )
            raise TimeoutError(
                f"Docker execution exceeded timeout of {timeout} seconds."
            ) from exc
        except DockerException as exc:
            if isinstance(exc, ImageNotFound):
                raise
            short_id = _short_container_id(
                metadata.get("container_id") or getattr(container, "id", None)
            )
            logger.error(
                "Docker execution failed.",
                image=self.image,
                container_id=short_id,
                error=str(exc),
            )
            if container is None:
                raise RuntimeError(
                    "Docker daemon unavailable or unable to start container. "
                    "Ensure Docker is running and accessible."
                ) from exc
            raise
        finally:
            context.cleanup()
            if container is not None:
                short_id = _short_container_id(
                    metadata.get("container_id") or container.id
                )
                try:
                    container.remove(force=True)
                    logger.info(
                        "Docker container removed.",
                        image=self.image,
                        container_id=short_id,
                    )
                except DockerException as cleanup_exc:
                    logger.warning(
                        "Failed to remove Docker container.",
                        image=self.image,
                        container_id=short_id,
                        error=str(cleanup_exc),
                    )

        return PythonExecutionResult(
            stdout=stdout_text,
            stderr=stderr_text,
            exit_code=exit_code,
            metadata=metadata,
            duration_seconds=duration,
        )


def create_requirements_file(
    dependencies: Sequence[str],
    work_dir: str | Path,
) -> Path:
    path = Path(work_dir)
    path.mkdir(parents=True, exist_ok=True)
    req = path / "requirements.txt"
    req.write_text("\n".join(sorted(set(dependencies))))
    return req


def install_dependencies(
    dependencies: Sequence[str],
    work_dir: str | Path,
    *,
    image: str = DEFAULT_IMAGE,
    timeout: int = 300,
) -> tuple[bool, str]:
    if not dependencies:
        return True, ""
    requirements = create_requirements_file(dependencies, work_dir)
    try:
        subprocess.run(
            ["pip", "install", "-r", str(requirements)],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        return True, ""
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        return False, exc.stderr.decode("utf-8", errors="ignore")


def _get_docker_client() -> DockerClient:
    try:
        return docker.from_env()
    except DockerException as exc:  # pragma: no cover - defensive
        raise RuntimeError("Cannot connect to Docker daemon") from exc


def _load_api_credentials() -> dict[str, str]:
    try:
        load_environment_variables_from_file()
    except (OSError, RuntimeError) as exc:  # pragma: no cover - defensive
        logger.debug(
            "Environment file could not be loaded; continuing without credentials.",
            error=str(exc),
        )
    credentials: dict[str, str] = {}
    for metadata in iter_api_metadata():
        value = os.getenv(metadata.key)
        if value:
            credentials[metadata.key] = value
    return credentials


def _is_transient_image_error(error: APIError) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code is not None:
        if status_code >= 500 or status_code in {408, 429}:
            return True
        if status_code in {400, 401, 403, 404}:
            return False

    message = str(error).lower()
    transient_tokens = (
        "timeout",
        "temporarily",
        "connection reset",
        "connection refused",
        "context deadline",
        "try again",
        "server error",
        "unavailable",
    )
    return any(token in message for token in transient_tokens)


def _pull_image_with_retry(
    client: DockerClient,
    image: str,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> None:
    attempt = 0
    while attempt < max_attempts:
        try:
            client.images.pull(image)
            return
        except ImageNotFound:
            raise
        except APIError as exc:
            attempt += 1
            status_code = getattr(exc, "status_code", None)
            if status_code is None:
                status_code = getattr(
                    getattr(exc, "response", None), "status_code", None
                )
            if status_code == 404:
                raise ImageNotFound(
                    exc.explanation or f"Image '{image}' not found.",
                    response=getattr(exc, "response", None),
                    explanation=getattr(exc, "explanation", None),
                ) from exc
            if not _is_transient_image_error(exc) or attempt >= max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.debug(
                "Retrying Docker image pull.",
                image=image,
                attempt=attempt,
                delay_seconds=delay,
            )
            time.sleep(delay)


def _short_container_id(identifier: str | None) -> str | None:
    if not identifier:
        return None
    return identifier[:12]


def resolve_work_dir(config: Any, *, default_run: str = "default_run") -> Path:
    value = getattr(config, "work_dir", None)
    if not value:
        value = Path(tempfile.gettempdir()) / "autodata" / default_run
    path = Path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path


def execute_with_dependencies(
    code: str,
    *,
    work_dir: str | Path,
    dependencies: Sequence[str] | None = None,
    image: str = DEFAULT_IMAGE,
    timeout: int = 300,
) -> PythonExecutionResult:
    executor = DockerPythonExecutor(work_dir, image=image)
    return executor.execute(code, timeout=timeout, dependencies=dependencies)


def sanitize_python_input(code: str) -> str:
    return code.replace("\r\n", "\n").strip()


def collect_runtime_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if isinstance(value, str)}


def generate_validation_filename(*, timestamp: datetime | None = None) -> str:
    """Return unique validation script filename following configuration pattern."""
    current = (timestamp or datetime.now(UTC)).strftime("%Y%m%d_%H%M%S")
    return f"validation_{current}_{uuid.uuid4().hex[:8]}.py"


__all__ = [
    "DEFAULT_IMAGE",
    "DockerPythonExecutor",
    "PythonExecutionResult",
    "PythonExecutor",
    "collect_runtime_env",
    "create_requirements_file",
    "execute_with_dependencies",
    "install_dependencies",
    "generate_validation_filename",
    "resolve_work_dir",
    "sanitize_python_input",
]


def execute_python_snippet(
    code: str,
    *,
    work_dir: str | Path,
    image: str = DEFAULT_IMAGE,
    dependencies: Sequence[str] | None = None,
    timeout: int = 300,
) -> str:
    result = execute_with_dependencies(
        code,
        work_dir=work_dir,
        dependencies=dependencies,
        image=image,
        timeout=timeout,
    )
    return result.stdout or result.stderr
