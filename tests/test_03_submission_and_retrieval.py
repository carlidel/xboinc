# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
########################################### #

import shutil
import tarfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xpart as xp
import xtrack as xt

import xboinc as xb


class TestConfig:
    """Configuration constants for submission and retrieval tests."""

    TEST_ACCOUNT = "camontan"
    # Directory paths
    BASE_DIR = Path(f"/afs/cern.ch/user/{TEST_ACCOUNT[0]}/{TEST_ACCOUNT}/test_xboinc")
    INPUT_DIR = BASE_DIR / "input_dev"
    OUTPUT_DIR = BASE_DIR / "output_dev"

    # File names
    INPUT_FILE = "xboinc_input.bin"
    OUTPUT_FILE = "xboinc_state_out.bin"
    CHECKPOINT_FILE = "checkpoint.bin"

    # Test parameters
    STUDY_NAME = "_test_study"
    NUM_TURNS = 100
    NUM_PARTICLES = 5000
    CHECKPOINT_EVERY = 25
    PARTICLES_PER_JOB = 500

    # Timing
    SUBMISSION_DELAY = 5  # seconds between submissions
    TAR_DELAY = 0.5  # seconds between tar operations
    TIMESTAMP_TOLERANCE = 60  # seconds for timestamp validation

    @classmethod
    def num_jobs(cls) -> int:
        """Calculate number of jobs based on particle distribution."""
        return int(cls.NUM_PARTICLES / cls.PARTICLES_PER_JOB)


@pytest.fixture(autouse=True)
def version_check_skip():
    """Skip xsuite version checking during tests."""
    xb._skip_xsuite_version_check = True
    yield
    xb._skip_xsuite_version_check = False


@pytest.fixture
def registered_user():
    """Ensure user is registered and cleanup after test."""
    xb.register(TestConfig.TEST_ACCOUNT, TestConfig.BASE_DIR)
    xb.register("testuser", TestConfig.BASE_DIR)
    yield TestConfig.TEST_ACCOUNT
    xb.deregister(TestConfig.TEST_ACCOUNT)
    xb.deregister("testuser")


@pytest.fixture
def clean_testuser_files():
    """Clean up test user tar files before and after tests."""
    output_dir = TestConfig.OUTPUT_DIR

    def cleanup():
        """Remove all files and directories that begin with 'testuser'."""
        for file_path in output_dir.glob(f"testuser__*"):
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()

    cleanup()
    yield
    cleanup()


@pytest.fixture
def clean_directories():
    """Clean test directories before and after tests."""

    def cleanup():
        """Remove all test files and directories."""
        for directory in [TestConfig.INPUT_DIR, TestConfig.OUTPUT_DIR]:
            for file_path in directory.glob(f"{TestConfig.TEST_ACCOUNT}__*"):
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

    cleanup()
    yield
    cleanup()


def create_test_line() -> xt.Line:
    """
    Create a simple test tracking line.

    Returns
    -------
    xt.Line
        A basic tracking line for testing.
    """
    return xt.Line(
        elements=[xt.Drift(length=1.0), xt.Multipole(knl=[1e-4]), xt.Drift(length=1.0)]
    )


def create_random_particles(
    num_particles: int, x_sigma: float = 0.01, y_sigma: float = 0.003
) -> xp.Particles:
    """
    Create particles with random initial conditions.

    Parameters
    ----------
    num_particles : int
        Number of particles to create.
    x_sigma : float
        Standard deviation for x distribution.
    y_sigma : float
        Standard deviation for y distribution.

    Returns
    -------
    xp.Particles
        Particles object with random initial conditions.
    """
    return xp.Particles(
        x=np.random.normal(0, x_sigma, num_particles),
        y=np.random.normal(0, y_sigma, num_particles),
    )


def submit_study_jobs(
    user: str,
    study_name: str,
    line: xt.Line,
    x_sigma: float = 0.01,
    y_sigma: float = 0.003,
) -> xb.JobManager:
    """
    Submit a complete study with multiple jobs.

    Parameters
    ----------
    user : str
        Username for job submission.
    study_name : str
        Name of the study.
    line : xt.Line
        Tracking line to use.
    x_sigma, y_sigma : float
        Particle distribution parameters.

    Returns
    -------
    xb.JobManager
        The job manager used for submission.
    """
    jobs = xb.JobManager(user=user, study_name=study_name, line=line, dev_server=True)

    for i in range(TestConfig.num_jobs()):
        particles = create_random_particles(
            TestConfig.PARTICLES_PER_JOB, x_sigma, y_sigma
        )
        jobs.add(
            job_name=f"{study_name}_job{i}",
            num_turns=TestConfig.NUM_TURNS,
            particles=particles,
            checkpoint_every=TestConfig.CHECKPOINT_EVERY,
        )

    jobs.submit()
    return jobs


def validate_tar_contents(tar_path: Path, expected_jobs: int, user: str) -> None:
    """
    Validate the contents of a submitted tar file.

    Parameters
    ----------
    tar_path : Path
        Path to the tar file to validate.
    expected_jobs : int
        Expected number of jobs in the tar.
    user : str
        Expected username in file names.
    """
    assert tar_path.exists() and tar_path.stat().st_size > 0

    with tarfile.open(tar_path) as tar_file:
        members = tar_file.getmembers()

        # Should have 2 files per job (json + bin)
        assert len(members) == 2 * expected_jobs

        # All files should have content
        assert all(member.size > 8 for member in members)

        member_names = [member.name for member in members]

        # Check file naming convention
        user_prefix = f"{user}__"
        assert all(name.startswith(user_prefix) for name in member_names)

        # Check file types
        json_files = [name for name in member_names if name.endswith(".json")]
        bin_files = [name for name in member_names if name.endswith(".bin")]

        assert len(json_files) == expected_jobs
        assert len(bin_files) == expected_jobs


def find_recent_tar(
    directory: Path, user: str, study_pattern: str, tolerance_seconds: int = 60
) -> Path:
    """
    Find the most recently created tar file matching the pattern.

    Parameters
    ----------
    directory : Path
        Directory to search in.
    user : str
        Username to match.
    study_pattern : str
        Study name pattern to match.
    tolerance_seconds : int
        Maximum age in seconds for "recent" files.

    Returns
    -------
    Path
        Path to the most recent matching tar file.
    """
    now = pd.Timestamp.now().timestamp()
    pattern = f"{user}__{study_pattern}__*"
    tar_files = list(directory.glob(pattern))

    for tar_path in tar_files:
        # Parse timestamp from filename
        timestamp_str = tar_path.name.split("__")[-1].split(".")[0]
        timestamp_str = (
            timestamp_str.replace("_", "T").replace("-", ":").replace(":", "-", 2)
        )

        try:
            file_timestamp = pd.Timestamp(timestamp_str).timestamp()
            if abs(now - file_timestamp) < tolerance_seconds:
                return tar_path
        except (ValueError, pd.errors.ParserError):
            continue

    raise FileNotFoundError(f"No recent tar file found matching {pattern}")


def test_submission(monkeypatch, registered_user, clean_directories):
    """Test job submission workflow with multiple studies."""
    monkeypatch.setattr(xb.submit, "LOWER_TIME_BOUND", 0.0)

    line = create_test_line()

    # Submit first study
    submit_study_jobs(
        registered_user, f"{TestConfig.STUDY_NAME}_1", line, x_sigma=0.01, y_sigma=0.003
    )

    # Test that adding jobs after submission fails
    jobs = xb.JobManager(
        registered_user, f"{TestConfig.STUDY_NAME}_temp", line=line, dev_server=True
    )
    jobs.submit()

    with pytest.raises(ValueError):
        jobs.add(
            job_name="test",
            num_turns=TestConfig.NUM_TURNS,
            line=line,
            particles=xp.Particles(),
            checkpoint_every=TestConfig.CHECKPOINT_EVERY,
        )

    time.sleep(TestConfig.SUBMISSION_DELAY)

    # Submit second study with different parameters
    submit_study_jobs(
        registered_user, f"{TestConfig.STUDY_NAME}_2", line, x_sigma=4.7, y_sigma=0.39
    )

    time.sleep(TestConfig.SUBMISSION_DELAY)

    # Test that production server raises NotImplementedError
    with pytest.raises(NotImplementedError):
        xb.JobManager(registered_user, f"{TestConfig.STUDY_NAME}_3", line=line)

    # Validate submitted tar files
    tar_files = list(
        TestConfig.INPUT_DIR.glob(f"{registered_user}__{TestConfig.STUDY_NAME}_?__*")
    )
    assert len(tar_files) == 2

    # Find and validate the most recent tar
    recent_tar = find_recent_tar(
        TestConfig.INPUT_DIR,
        registered_user,
        f"{TestConfig.STUDY_NAME}_?",
        TestConfig.TIMESTAMP_TOLERANCE,
    )
    validate_tar_contents(recent_tar, TestConfig.num_jobs(), registered_user)


def test_retrieval(registered_user):
    """Test job result retrieval and validation."""
    # prepare the mock output tar files
    output_dir = TestConfig.OUTPUT_DIR

    mock_tar_files_dir = xb._pkg_root.parent / "tests" / "data" / "example_output"

    for tar_file in mock_tar_files_dir.glob("*.tar.gz"):
        print(f"Copying {tar_file} to {output_dir}")
        shutil.copy(tar_file, output_dir)

    # Iterate through jobs and validate results
    for _, result_particles in xb.ResultRetriever.iterate(
        "testuser", "example_study_fourth", dev_server=True
    ):
        assert len(result_particles.x) == 100
