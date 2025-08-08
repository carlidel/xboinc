# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

"""
Job submission management for the Xboinc BOINC server.

This module provides the JobManager class for managing and submitting particle tracking
jobs to the Xboinc BOINC server. It handles job preparation, validation, packaging,
and submission with proper time estimation and resource management.

The module includes:
- Job time estimation based on benchmark data
- Job validation for time bounds
- Batch submission capabilities
- Support for both development and production servers
"""

import datetime
import json
import tarfile
from time import sleep
from warnings import warn

import numpy as np
import xobjects as xo
from tqdm.auto import tqdm

from xaux import FsPath, eos_accessible
from xaux.fs.temp import _tempdir

from .server import timestamp
from .simulation_io import XbInput, app_version, assert_versions
from .user import get_directory, get_domain

BENCHMARK_DATA = {
    "mean_scaling_factor": 2.7625854392188003e-09,  # second per turn per particle per element
    "std_scaling_factor": 2.567704406008288e-10,
    "final_scaling_factor": 3.019355879819629e-09,  # mean + std
    "comment": "Evaluated on a 12th Gen Intel i7-12700",
}

LOWER_TIME_BOUND = 90  # seconds, minimum time for a job to be considered valid
UPPER_TIME_BOUND = 3 * 24 * 60 * 60  # seconds, maximum time, 3 days

# For now, let's set a size limit of 1GB for job inputs, set constant in bytes
XB_INPUT_SIZE_LIMIT = 1 * 1024 * 1024 * 1024  # 1GB


def _get_num_elements_from_line(line):
    """
    Extract element count statistics from a tracking line.

    Parameters
    ----------
    line : xtrack.Line or None
        The tracking line containing elements to analyze.

    Returns
    -------
    dict, int
        Dictionary mapping element class names to their counts in the line and
        the total number of elements.
        Returns empty dict and zero if line is None.

    Examples
    --------
    >>> line = xtrack.Line.from_dict(line_dict)
    >>> elements = _get_num_elements_from_line(line)
    >>> print(elements)
    {'Drift': 100, 'Quadrupole': 50, 'Bend': 25}
    """
    if line is None:
        return {}, 0
    elements = np.unique(
        [ee.__class__.__name__ for ee in line.elements], return_counts=True
    )
    return dict(zip(*elements)), elements[1].sum()


class JobManager:
    """
    A class to manage jobs for submission to the Xboinc server.

    This class provides a convenient interface for adding multiple particle tracking
    jobs and submitting them as a batch to the BOINC server. It handles job validation,
    time estimation, file preparation, and submission.

    The JobManager ensures that:
    - Job execution times fall within acceptable bounds
    - Job names are unique within a study
    - All necessary files are properly packaged and submitted
    - Proper cleanup is performed after submission

    Attributes
    ----------
    dev_server : bool
        Whether jobs are submitted to the development server.

    Examples
    --------
    Basic usage with a single line for all jobs:

    >>> line = xtrack.Line.from_dict(line_dict)
    >>> manager = JobManager("user123", "my_study", line=line, dev_server=True)
    >>> manager.add(job_name="job1", num_turns=1000, particles=particles1)
    >>> manager.add(job_name="job2", num_turns=2000, particles=particles2)
    >>> manager.submit()

    Usage with different lines per job:

    >>> manager = JobManager("user123", "my_study", dev_server=True)
    >>> manager.add(job_name="job1", num_turns=1000, particles=particles1, line=line1)
    >>> manager.add(job_name="job2", num_turns=2000, particles=particles2, line=line2)
    >>> manager.submit()
    """

    def __init__(self, user, study_name, line=None, dev_server=False, **kwargs):
        """
        Initialize a new JobManager instance.

        Parameters
        ----------
        user : str
            The username for BOINC submission. The user must be a member of the
            CERN xboinc-submitters egroup and have proper permissions set.
        study_name : str
            The name of the study. This will be included in job metadata and
            used for organizing submissions. Cannot contain '__' (double underscore).
        line : xtrack.Line, optional
            The tracking line to be used for all jobs. If provided here, it will
            be preprocessed once and reused for all jobs, improving performance.
            If None, must be provided for each job individually in add().
        dev_server : bool, optional
            Whether to submit to the development server. Defaults to False.
            Currently, only the dev server is operational.
        **kwargs
            Additional keyword arguments for future extensibility.

        Raises
        ------
        ValueError
            If study_name contains '__' (double underscore).
        NotImplementedError
            If dev_server is False (regular server not yet operational).
        AssertionError
            If EOS is required but not accessible.

        Notes
        -----
        The JobManager creates a temporary directory for file preparation and
        validates that the user has access to the required storage systems.
        """

        assert_versions()
        if not dev_server:
            raise NotImplementedError(
                "Regular server not yet operational. " + "Please use dev_server=True."
            )
        self.dev_server = dev_server
        if "__" in study_name:
            raise ValueError(
                "The character sequence '__' is not allowed in 'study_name'!"
            )
        self._user = user
        self._domain = get_domain(user)
        if self._domain == "eos":
            assert (
                eos_accessible
            ), "EOS is not accessible! Please check your connection."
        if self.dev_server:
            self._target = get_directory(user) / "input_dev"
        else:
            self._target = get_directory(user) / "input"
        self._study_name = study_name
        self._line = line
        self._num_elements, self._total_elements = _get_num_elements_from_line(line)
        self._submit_file = f"{self._user}__{self._study_name}__{timestamp()}.tar.gz"
        self._json_files = []
        self._bin_files = []
        self._tempdir = FsPath(_tempdir.name).resolve()
        self._submitted = False
        self._unique_job_names = set()

    def _assert_not_submitted(self):
        """
        Ensure that jobs have not already been submitted.

        Raises
        ------
        ValueError
            If jobs have already been submitted from this JobManager instance.
        """
        if self._submitted:
            raise ValueError(
                "Jobs already submitted! Make a new JobManager object to continue."
            )

    def add(
        self,
        *,
        job_name,
        num_turns,
        ele_start=0,
        ele_stop=-1,
        particles,
        line=None,
        checkpoint_every=-1,
        **kwargs,
    ):
        """
        Add a single job to the JobManager instance.

        This method creates the necessary input files (binary and JSON metadata)
        for a single tracking job. The job is validated for execution time bounds
        and prepared for batch submission.

        Parameters
        ----------
        job_name : str
            Unique name for this job within the study. Cannot contain '__'
            (double underscore). If a duplicate name is provided, it will be
            automatically renamed with a numeric suffix.
        num_turns : int
            The number of tracking turns for this job. Must be positive.
        ele_start : int, optional
            The starting element index for tracking. Default is 0 (first element).
            If provided different from 0 with particles set at a certain starting
            position, raises a ValueError.
        ele_stop : int, optional
            The stopping element index for tracking. Default is -1 (last element).
        particles : xpart.Particles
            The particles object containing the initial particle distribution
            to be tracked.
        line : xtrack.Line, optional
            The tracking line for this specific job. If None, uses the line
            provided during JobManager initialization. Providing a line per
            job is slower due to repeated preprocessing.
        checkpoint_every : int, optional
            Checkpoint interval in turns. Default is -1 (no checkpointing).
            If positive, simulation state will be saved every N turns.
        **kwargs
            Additional job metadata to be included in the job JSON file.

        Raises
        ------
        ValueError
            If job_name contains '__', if no line is available, or if the
            estimated execution time is outside acceptable bounds.

        Notes
        -----
        Job execution time is estimated using benchmark data and must fall
        between LOWER_TIME_BOUND (90s) and UPPER_TIME_BOUND (3 days).

        The method creates two files per job:
        - A .json file with job metadata
        - A .bin file with the binary simulation input data

        Examples
        --------
        >>> manager.add(
        ...     job_name="scan_point_1",
        ...     num_turns=10000,
        ...     particles=my_particles,
        ...     custom_param=42
        ... )
        """

        self._assert_not_submitted()
        if "__" in job_name:
            raise ValueError(
                "The character sequence '__' is not allowed in 'job_name'!"
            )

        if job_name in self._unique_job_names:
            warn(
                f"The job name '{job_name}' has already been added. "
                "The job will be renamed to avoid conflicts."
            )
            # check if the job name ends with a number after an underscore
            if "_" in job_name:
                parts = job_name.rsplit("_", 1)
                if parts[-1].isdigit():
                    job_name = f"{parts[0]}_{int(parts[-1]) + 1}"
                else:
                    job_name = f"{job_name}_1"
            else:
                job_name = f"{job_name}_1"

        self._unique_job_names.add(job_name)

        # Get the line from kwargs, and default to the line in JobManager
        if line is None:
            if self._line is None:
                raise ValueError(
                    "Need to provide a line! This can be done for "
                    + "each job separately, or at the JobManager init."
                )
            line = self._line
            num_elements = self._num_elements
            total_elements = self._total_elements
        else:
            # If a new line is given, preprocess it
            num_elements, total_elements = _get_num_elements_from_line(line)

        sleep(0.001)  # To enforce different filenames
        filename = f"{self._user}__{timestamp(ms=True)}"
        json_file = FsPath(self._tempdir, f"{filename}.json")
        bin_file = FsPath(self._tempdir, f"{filename}.bin")

        # block if job expected to be too short or too long
        expected_time = (
            num_turns
            * len(particles.x)
            * total_elements
            * BENCHMARK_DATA["final_scaling_factor"]
        )
        datetime_expected = datetime.timedelta(seconds=expected_time)

        if expected_time < LOWER_TIME_BOUND:
            raise ValueError(
                f"Expected time for job {job_name} is too short ({expected_time:.2f} seconds, minimum is {LOWER_TIME_BOUND:.2f} seconds). "
                "Please increase the number of particles in the job or consider "
                "running it locally instead."
            )
        if expected_time > UPPER_TIME_BOUND:
            datetime_max = datetime.timedelta(seconds=UPPER_TIME_BOUND)
            raise ValueError(
                f"Expected time for job {job_name} is too long ({datetime_expected}, maximum is {datetime_max.days}). "
                "Please split the job into smaller parts with fewer particles."
            )

        json_dict = {
            "user": self._user,
            "study_name": self._study_name,
            "job_name": job_name,
            "xboinc_ver": app_version,
            "num_elements": num_elements,
            "num_part": len(particles.state[particles.state > 0]),
            "num_turns": num_turns,
            **kwargs,
        }
        with json_file.open("w", encoding="utf-8") as fid:
            json.dump(json_dict, fid, cls=xo.JEncoder)
        data = XbInput(
            num_turns=num_turns,
            line=line,
            checkpoint_every=checkpoint_every,
            particles=particles,
            store_element_names=False,
            ele_start=ele_start,
            ele_stop=-ele_stop,
        )

        # check the size of data
        if data._buffer.capacity > XB_INPUT_SIZE_LIMIT:
            raise ValueError(
                f"Input data size of {data._buffer.capacity} bytes exceeds limit of {XB_INPUT_SIZE_LIMIT} bytes. "
                "Please reduce the size of the job by revising the number of particles or the extent of the monitors included."
            )

        data.to_binary(bin_file)
        self._json_files += [json_file]
        self._bin_files += [bin_file]
        print(
            f"Added job {job_name} for user {self._user} in study {self._study_name} "
            + f"with {len(particles.x)} particles and {num_turns} turns."
            + f" Expected execution time: {datetime_expected}."
        )

    def submit(self):
        """
        Package and submit all added jobs to the BOINC server.

        This method creates a compressed tar archive containing all job files
        and moves it to the user's submission directory where the BOINC server
        will periodically check for new submissions.

        The submission process:
        1. Creates a .tar.gz archive with all job files
        2. Moves the archive to the appropriate submission directory
        3. Cleans up temporary files
        4. Marks the JobManager as submitted

        Raises
        ------
        ValueError
            If jobs have already been submitted or if the user domain is invalid.

        Notes
        -----
        After submission, this JobManager instance cannot be used to add more
        jobs. Create a new JobManager instance for additional submissions.

        The submission directory depends on the dev_server setting:
        - Development server: {user_directory}/input_dev
        - Production server: {user_directory}/input

        Examples
        --------
        >>> manager.submit()
        Zipping files: 100%|██████████| 4/4 [00:00<00:00, 1234.56it/s]
        Submitted 2 jobs to BOINC server for user user123 in study my_study.
        """

        self._assert_not_submitted()
        with tarfile.open(self._tempdir / self._submit_file, "w:gz") as tar:
            for thisfile in tqdm(
                self._json_files + self._bin_files, desc="Zipping files"
            ):
                tar.add(thisfile, arcname=thisfile.name)
        if self._domain in ["eos", "afs"]:
            FsPath(self._tempdir / self._submit_file).move_to(self._target)
        else:
            raise ValueError(f"Wrong domain {self._domain} for user {self._user}!")
        self._submitted = True
        # clean up
        for thisfile in self._json_files + self._bin_files:
            thisfile.unlink()
        # self._temp.cleanup()

        print(
            f"Submitted {len(self._json_files)} jobs to BOINC server for user "
            + f"{self._user} in study {self._study_name}."
        )

    def __len__(self):
        """
        Return the number of jobs added to this JobManager instance.

        Returns
        -------
        int
            The number of jobs that have been added but not yet submitted.
        """
        return len(self._json_files)

    def __repr__(self):
        """
        Return a string representation of the JobManager instance.

        Returns
        -------
        str
            A concise string representation showing key attributes and status.

        Examples
        --------
        >>> manager = JobManager("user123", "my_study", dev_server=True)
        >>> repr(manager)
        'JobManager(user=user123, study_name=my_study, num_jobs=0, dev_server=True, submitted=False)'
        """
        return (
            f"JobManager(user={self._user}, study_name={self._study_name}, "
            + f"num_jobs={len(self)}, dev_server={self.dev_server}, submitted={self._submitted})"
        )

    def get_job_summary(self):
        """
        Return a comprehensive summary of all jobs in this JobManager instance.

        Returns
        -------
        dict
            A dictionary containing:
            - user: The submitting user
            - study_name: The study name
            - num_jobs: Total number of jobs
            - dev_server: Whether using development server
            - jobs: List of individual job summaries with name, turns, and particle count
            - submitted: Whether jobs have been submitted

        Examples
        --------
        >>> summary = manager.get_job_summary()
        >>> print(f"Study {summary['study_name']} has {summary['num_jobs']} jobs")
        >>> for job in summary['jobs']:
        ...     print(f"Job {job['job_name']}: {job['num_particles']} particles, {job['num_turns']} turns")
        """
        return {
            "user": self._user,
            "study_name": self._study_name,
            "num_jobs": len(self),
            "dev_server": self.dev_server,
            "jobs": [
                {
                    "job_name": job["job_name"],
                    "num_turns": job["num_turns"],
                    "num_particles": job["num_part"],
                }
                for job in self._json_files
            ],
            "submitted": self._submitted,
        }
