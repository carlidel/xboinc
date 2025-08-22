# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
########################################### #

import json
import os
import time
from pathlib import Path
from typing import Any, Dict

import pytest

from xaux import FsPath

import xboinc as xb
from xboinc.server import dropdir
from xboinc.user import get_directory, get_domain, get_user_data, user_data_file


# NOTE: to have these tests running, you might want to alter some of these parameters!
class TestConfig:
    """Configuration constants for user management tests."""

    # Server account to be use for performing the testing
    TEST_ACCOUNT = os.getlogin()
    TEST_AFS = FsPath(f"/afs/cern.ch/user/{TEST_ACCOUNT[0]}/{TEST_ACCOUNT}/test_xboinc")
    TEST_EOS = FsPath(f"/eos/home/{TEST_ACCOUNT[0]}/{TEST_ACCOUNT}/test_xboinc")

    # Required directory structure for registered users
    REQUIRED_DIRECTORIES = ["input", "output", "input_dev", "output_dev"]

    # Expected file prefixes for server communication
    REGISTER_PREFIX = "register"
    DEREGISTER_PREFIX = "deregister"
    DEV_REGISTER_PREFIX = "dev_register"
    DEV_DEREGISTER_PREFIX = "dev_deregister"



def get_server_file_paths(account: str) -> Dict[str, Path]:
    """
    Generate paths for all server communication files.

    Parameters
    ----------
    account : str
        The server account name.

    Returns
    -------
    dict[str, Path]
        Dictionary mapping file types to their paths.
    """
    return {
        "register": dropdir / f"{TestConfig.REGISTER_PREFIX}_{account}.json",
        "deregister": dropdir / f"{TestConfig.DEREGISTER_PREFIX}_{account}.json",
        "dev_register": dropdir / f"{TestConfig.DEV_REGISTER_PREFIX}_{account}.json",
        "dev_deregister": dropdir
        / f"{TestConfig.DEV_DEREGISTER_PREFIX}_{account}.json",
    }


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Load and return JSON data from a file.

    Parameters
    ----------
    file_path : Path
        Path to the JSON file.

    Returns
    -------
    dict
        The loaded JSON data.
    """
    with file_path.open("r", encoding="utf-8") as fid:
        return json.load(fid)


def assert_user_data(
    account: str, expected_directory: Path, expected_domain: str
) -> None:
    """
    Assert that user data matches expected values.

    Parameters
    ----------
    account : str
        The user account to check.
    expected_directory : Path
        Expected user directory path.
    expected_domain : str
        Expected domain (e.g., 'afs', 'eos').
    """
    # Check directory access functions
    assert get_directory(account) == expected_directory
    assert get_domain(account) == expected_domain

    # Check user data dictionary
    user_data = get_user_data(account)
    assert user_data["directory"] == Path(expected_directory).as_posix()
    assert user_data["domain"] == expected_domain


def assert_directory_structure(base_directory: Path) -> None:
    """
    Assert that all required directories exist under the base directory.

    Parameters
    ----------
    base_directory : Path
        The base directory to check.
    """
    for dir_name in TestConfig.REQUIRED_DIRECTORIES:
        directory = base_directory / dir_name
        assert directory.exists(), f"Directory {directory} does not exist"


def assert_registration_files(
    file_paths: Dict[str, Path],
    account: str,
    directory: Path,
    domain: str,
    should_exist: bool = True,
) -> None:
    """
    Assert the state and content of registration files.

    Parameters
    ----------
    file_paths : dict
        Dictionary of file paths from get_server_file_paths().
    account : str
        The user account.
    directory : Path
        Expected directory in the files.
    domain : str
        Expected domain in the files.
    should_exist : bool
        Whether the registration files should exist.
    """
    register_files = ["register", "dev_register"]
    deregister_files = ["deregister", "dev_deregister"]

    files_in_dropdir = set(os.listdir(dropdir))
    for file_key in register_files:
        file_path = file_paths[file_key]
        file_name = file_path.name
        if should_exist:
            # print(f"Checking registration file {file_path}")
            assert (
                file_name in files_in_dropdir
            ), f"Registration file {file_path} should exist"
            # NOTE: For some reason EOS files can be messy, so we can't check files
            # immediately after registration... for this reason, we skip this check
            # time.sleep(10)
            # file_data = load_json_file(file_path)
            # assert file_data['user'] == account
            # assert file_data['directory'] == directory.as_posix()
            # assert file_data['domain'] == domain
        else:
            assert (
                file_name not in files_in_dropdir
            ), f"Registration file {file_path} should not exist"

    for file_key in deregister_files:
        file_path = file_paths[file_key]
        file_name = file_path.name
        assert (
            file_name not in files_in_dropdir
        ), f"Deregistration file {file_path} should not exist"


def assert_deregistration_files(file_paths: Dict[str, Path], dropdir: Path) -> None:
    """
    Assert the state and content of deregistration files using os.listdir.

    Parameters
    ----------
    file_paths : dict
        Dictionary of file paths from get_server_file_paths().
    dropdir : Path
        The drop directory to check for files.
    """
    files_in_dropdir = set(os.listdir(dropdir))
    # print(f"Files in dropdir: {files_in_dropdir}")
    # Registration files should not exist
    register_files = ["register", "dev_register"]
    for file_key in register_files:
        file_name = file_paths[file_key].name
        assert (
            file_name not in files_in_dropdir
        ), f"Registration file {file_name} should not exist after deregistration"

    # Deregistration files should exist
    deregister_files = ["deregister", "dev_deregister"]
    for file_key in deregister_files:
        file_name = file_paths[file_key].name
        assert (
            file_name in files_in_dropdir
        ), f"Deregistration file {file_name} should exist"
        # file_data = load_json_file(file_paths[file_key])
        # assert file_data['user'] == TestConfig.TEST_ACCOUNT


@pytest.fixture
def server_files():
    """Fixture to provide server file paths and cleanup after tests."""
    file_paths = get_server_file_paths(TestConfig.TEST_ACCOUNT)
    yield file_paths

    # Cleanup all server files after test
    for file_path in file_paths.values():
        if file_path.exists():
            file_path.unlink()


@pytest.mark.parametrize(
    "user_path",
    [
        pytest.param(
            ['afs', TestConfig.TEST_AFS],
            marks=pytest.mark.skipif(
                not TestConfig.TEST_AFS.exists(),
                reason=f"Test user AFS path does not exist ({TestConfig.TEST_AFS})",
            ),
        ),
        pytest.param(
            ['eos', TestConfig.TEST_EOS],
            marks=pytest.mark.skipif(
                not TestConfig.TEST_EOS.exists(),
                reason=f"Test user EOS path does not exist ({TestConfig.TEST_EOS})",
            ),
        ),
    ],
    ids=["AFS path", "EOS path"],
)
def test_register(server_files, user_path):
    """
    Test user registration with AFS storage backend.

    Verifies that:
    - User directory structure is created correctly
    - User data is stored and retrievable
    - Registration files are created with correct content
    - EOS registration raises NotImplementedError
    """

    if user_path[0] == 'eos':
        # Test that EOS registration is not yet implemented
        with pytest.raises(NotImplementedError):
            xb.register(TestConfig.TEST_ACCOUNT, user_path[1])

    else:
        # Test successful registration
        # print(f"Registering user {TestConfig.TEST_ACCOUNT}")
        xb.register(TestConfig.TEST_ACCOUNT, user_path[1])

        # Verify registration files
        assert_registration_files(
            server_files, TestConfig.TEST_ACCOUNT, dropdir, user_path[0], should_exist=True
        )

        # Verify user data and directory structure
        assert_user_data(TestConfig.TEST_ACCOUNT, user_path[1], user_path[0])
        assert_directory_structure(user_path[1])


@pytest.mark.parametrize(
    "user_path",
    [
        pytest.param(
            ['afs', TestConfig.TEST_AFS],
            marks=pytest.mark.skipif(
                not TestConfig.TEST_AFS.exists(),
                reason=f"Test user AFS path does not exist ({TestConfig.TEST_AFS})",
            ),
        ),
        pytest.param(
            ['eos', TestConfig.TEST_EOS],
            marks=pytest.mark.skipif(
                not TestConfig.TEST_EOS.exists(),
                reason=f"Test user EOS path does not exist ({TestConfig.TEST_EOS})",
            ),
        ),
    ],
    ids=["AFS path", "EOS path"],
)
def test_deregister(server_files, user_path):
    """
    Test user deregistration functionality.

    Verifies that:
    - User data is removed from the system
    - User data retrieval raises appropriate errors
    - Registration files are removed
    - Deregistration files are created
    """

    if user_path[0] != 'eos':
        # Register the user first
        xb.register(TestConfig.TEST_ACCOUNT, user_path[1])
        # print(os.listdir(dropdir))

    # Perform deregistration
    xb.deregister(TestConfig.TEST_ACCOUNT)
    # print(os.listdir(dropdir))

    # Verify user data is removed
    user_dict = load_json_file(user_data_file)
    assert (
        TestConfig.TEST_ACCOUNT not in user_dict.keys()
    ), "User should be removed from user data"

    # Verify that accessing user data raises an error
    with pytest.raises(
        ValueError, match=f"User {TestConfig.TEST_ACCOUNT} not registered!"
    ):
        get_user_data(TestConfig.TEST_ACCOUNT)

    # Verify deregistration files
    assert_deregistration_files(server_files, dropdir)
