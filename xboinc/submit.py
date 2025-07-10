# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2024.                 #
# ######################################### #

import json
import tarfile
import numpy as np
from time import sleep

import xobjects as xo
import xtrack as xt
from xaux import FsPath, eos_accessible
from xaux.fs.temp import _tempdir

from .user import get_domain, get_directory
from .server import timestamp
from .simulation_io import XbInput, app_version, assert_versions


_line_options = {
    "store_element_names": False,
    "remove_markers": True,
    "remove_zero_length_drifts": True,
    "remove_inactive_multipoles": True,
    "remove_redundant_apertures": True,
    "merge_consecutive_multipoles": True,
    "merge_consecutive_drifts": True,
    "use_simple_bends": False,
    "use_simple_quadrupoles": False,
}


def _preprocess_line(line, options):
    if line is None:
        return None
    has_tracker = False
    this_options = options.copy()
    this_options.pop("store_element_names")
    if not any(this_options.values()):
        # No reason to discard and rebuild tracker
        return line
    if line.tracker is not None:
        has_tracker = True
        buffer = line._buffer
        io_buffer = line.tracker.io_buffer
        line.discard_tracker()
    # Optimise
    if not this_options["remove_markers"]:
        line.remove_markers()
    if not this_options["remove_zero_length_drifts"]:
        line.remove_zero_length_drifts()
    if not this_options["remove_inactive_multipoles"]:
        line.remove_inactive_multipoles()
    if this_options["remove_redundant_apertures"]:
        line.remove_redundant_apertures()
    if this_options["merge_consecutive_multipoles"]:
        line.merge_consecutive_multipoles()
    if this_options["merge_consecutive_drifts"]:
        line.merge_consecutive_drifts()
    if this_options["use_simple_bends"]:
        line.use_simple_bends()
    if this_options["use_simple_quadrupoles"]:
        line.use_simple_quadrupoles()
    # Rebuild tracker if it was present
    if has_tracker:
        line.build_tracker(_buffer=buffer, io_buffer=io_buffer)
    return line


def _get_num_elements_from_line(line):
    if line is None:
        return {}
    elements = np.unique(
        [ee.__class__.__name__ for ee in line.elements], return_counts=True
    )
    return dict(zip(*elements))


class SubmitJobs:

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

        Additionally, the following optimisation flags can be passed
        globally:
            store_element_names : default False.
            remove_markers : default True.
            remove_zero_length_drifts : default True.
            remove_inactive_multipoles : default True.
            remove_redundant_apertures : default True.
            merge_consecutive_multipoles : default True.
            merge_consecutive_drifts : default True.
            use_simple_bends : default False.
            use_simple_quadrupoles : default False.

        Usage
        -----
        Create one SubmitJobs instance per study, add jobs one-by-one with
        SubmitJobs.add(), and submit with SubmitJobs.submit().
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
        self._line_options = {k: kwargs.pop(k, v) for k, v in _line_options.items()}
        self._line = _preprocess_line(line, self._line_options)
        self._num_elements = _get_num_elements_from_line(line)
        self._submit_file = f"{self._user}__{self._study_name}__{timestamp()}.tar.gz"
        self._json_files = []
        self._bin_files = []
        self._tempdir = FsPath(_tempdir.name).resolve()
        self._submitted = False

    def _assert_not_submitted(self):
        if self._submitted:
            raise ValueError(
                "Jobs already submitted! Make a new SubmitJobs object to continue."
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
        Add a single job to the SubmitJobs instance. This will create a binary input file and a
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

        # Get the line options from kwargs, and default to the options in SubmitJobs
        _line_options = {k: kwargs.pop(k, v) for k, v in self._line_options.items()}

        # Get the line from kwargs, and default to the line in SubmitJobs
        if line is None:
            if self._line is None:
                raise ValueError(
                    "Need to provide a line! This can be done for "
                    + "each job separately, or at the SubmitJobs init."
                )
            if not xt.line._dicts_equal(_line_options, self._line_options):
                raise ValueError(
                    f"Some different line options are given to job "
                    + f"{job_name}, compared to the options in SubmitJobs, "
                    + f"but no new line given!"
                )
            line = self._line
            num_elements = self._num_elements
        else:
            # If a new line is given, preprocess it
            line = _preprocess_line(line, _line_options)
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
        with json_file.open("w") as fid:
            json.dump(json_dict, fid, cls=xo.JEncoder)
        store_element_names = _line_options["store_element_names"]
        data = XbInput(
            num_turns=num_turns,
            line=line,
            checkpoint_every=checkpoint_every,
            particles=particles,
            store_element_names=store_element_names,
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
