import os
from typing import Generator
from uuid import uuid4
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def test_dir() -> Path:
    """Get the testing directory"""
    return Path(__file__).absolute().parent.parent


@pytest.fixture(scope="session")
def resource_dir() -> Path:
    """Get the testing directory"""
    return Path(__file__).absolute().parent.parent / "resources"


@pytest.fixture
def url() -> Generator[str, None, None]:
    file = f"/tmp/{str(uuid4())}.ipc"
    url = f"ipc://{file}"

    assert not Path(file).exists()
    yield url

    if Path(file).exists():
        os.remove(file)
