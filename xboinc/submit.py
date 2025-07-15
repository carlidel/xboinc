# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

import json
import tarfile
from time import sleep

import numpy as np
import xobjects as xo
import xtrack as xt

from xaux import FsPath, eos_accessible
from xaux.fs.temp import _tempdir

from .server import timestamp
from .simulation_io import XbInput, app_version, assert_versions
from .user import get_directory, get_domain


def _get_num_elements_from_line(line):
    if line is None:
        return {}
    elements = np.unique(
        [ee.__class__.__name__ for ee in line.elements], return_counts=True
    )
    return dict(zip(*elements))


class JobManager:

    def __init__(self, user, study_name, line=None, dev_server=False, **kwargs):
        """
        Parameters
        ----------
        user : string
            The user that submits to BOINC. Make sure all permissions are set
            (the user should be member of the CERN xboinc-submitters egroup).
        study_name : string
            The name of the study. This will go inside the job jsons and the
            filenames of the tars.
        line : xtrack.Line, optional
            The line to be tracked. Can be provided globally at the class
            construction, or for each job separately. The latter is much
            slower as it will be preprocessed at each job addition.
        dev_server: bool, optional
            Whether or not to submit to the dev server. Defaults to False.

        Usage
        -----
        Create one JobManager instance per study, add jobs one-by-one with
        JobManager.add(), and submit with JobManager.submit().
        """

        assert_versions()
        if not dev_server:
            raise NotImplementedError(
                "Regular server not yet operational. " + "Please use dev_server=True."
            )
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
        if dev_server:
            self._target = get_directory(user) / "input_dev"
        else:
            self._target = get_directory(user) / "input"
        self._study_name = study_name
        self._line = line
        self._num_elements = _get_num_elements_from_line(line)
        self._submit_file = f"{self._user}__{self._study_name}__{timestamp()}.tar.gz"
        self._json_files = []
        self._bin_files = []
        self._tempdir = FsPath(_tempdir.name).resolve()
        self._submitted = False

    def _assert_not_submitted(self):
        if self._submitted:
            raise ValueError(
                "Jobs already submitted! Make a new JobManager object to continue."
            )

    def add(
        self,
        *,
        job_name,
        num_turns,
        particles,
        line=None,
        checkpoint_every=-1,
        **kwargs,
    ):
        """
        Add a single job to the JobManager instance. This will create a binary input file and a
        json file (with the same name) containing the job metadata.

        Parameters
        ----------
        job_name : dict
            Name of this individual job.
        num_turns : int
            The number of turns this job should track.
        particles : xpart.Particles
            The particles to be tracked.
        line : xtrack.Line, optional
            The line to be tracked. Can be provided globally at the class
            construction, or here, for each job separately. The latter is
            much slower as it will be preprocessed at each job addition.
        checkpoint_every : int, optional
            When to checkpoint. The default value -1 represents no
            checkpointing.

        Returns
        -------
        None.
        """

        self._assert_not_submitted()
        if "__" in job_name:
            raise ValueError(
                "The character sequence '__' is not allowed in 'job_name'!"
            )

        # Get the line from kwargs, and default to the line in JobManager
        if line is None:
            if self._line is None:
                raise ValueError(
                    "Need to provide a line! This can be done for "
                    + "each job separately, or at the JobManager init."
                )
            line = self._line
            num_elements = self._num_elements
        else:
            # If a new line is given, preprocess it
            num_elements = _get_num_elements_from_line(line)

        sleep(0.001)  # To enforce different filenames
        filename = f"{self._user}__{timestamp(ms=True)}"
        json_file = FsPath(self._tempdir, f"{filename}.json")
        bin_file = FsPath(self._tempdir, f"{filename}.bin")
        # TODO: warn if job expected to be too short ( < 90s)
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
        )
        data.to_binary(bin_file)
        self._json_files += [json_file]
        self._bin_files += [bin_file]

    def submit(self):
        """
        Zip all files into a tarfile, and move it to the dedicated user
        folder for submission, which the BOINC server will periodically
        query for new submissions.

        Parameters
        ----------
        None.

        Returns
        -------
        None.
        """

        self._assert_not_submitted()
        with tarfile.open(self._tempdir / self._submit_file, "w:gz") as tar:
            for thisfile in self._json_files + self._bin_files:
                tar.add(thisfile, arcname=thisfile.name)
        if self._domain in ["eos", "afs"]:
            FsPath(self._tempdir / self._submit_file).move_to(self._target)
        else:
            raise ValueError(f"Wrong domain {self._domain} for user {self._user}!")
        self._submitted = True
        # TODO: check that tar contains all files
        # clean up
        for thisfile in self._json_files + self._bin_files:
            thisfile.unlink()
        # self._temp.cleanup()
