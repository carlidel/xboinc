# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

import json

from xaux import eos_accessible

from .server.tools import untar
from .simulation_io import XbState, assert_versions
from .user import get_directory, get_domain


class RetrieveJobs:

    def __init__(self, user, study_name, dev_server=False):
        """
        Parameters
        ----------
        user : string
            The user that submitted to BOINC. Make sure all permissions are set
            (the user should be member of the CERN xboinc-submitters egroup).
        study_name : string
            The name of the study to look for.
        dev_server: bool
            Whether or not to retrieve from the dev server. Defaults to False.

        Usage
        -----
        And RetrieveJobs instance works as an interator. Loop over it to
        retrieve a tuple (xpart.Particles, json_file) per finished job.
        """

        if not dev_server:
            raise NotImplementedError(
                "Regular server not yet operational. " + "Please use dev_server=True."
            )
        assert_versions()
        self._study_name = study_name
        self._user = user
        self._domain = get_domain(user)
        if self._domain == "eos":
            assert (
                eos_accessible
            ), "EOS is not accessible! Please check your connection."
        if dev_server:
            self._directory = get_directory(user) / "output_dev"
        else:
            self._directory = get_directory(user) / "output"
        self._to_delete = []
        # Untar all results, also if not from this study, as it is not
        # known yet which study's jobs are in which result tar.
        for tar_file in self._directory.glob("*.tar.gz"):
            untar(tar_file)

    def _clean(self):
        for json_file in self._to_delete:
            json_file.with_suffix(".bin").unlink()
            json_file.unlink()
        # Delete empty folders
        for folder in self._directory.glob("*/"):
            if not any(folder.iterdir()):
                folder.rmdir()

    def __iter__(self):
        # Create an iterator over all results that are from this study only.
        json_files = []
        for json_file in self._directory.glob("*/*.json"):
            with open(json_file, "r") as json_file_obj:
                json_content = json.load(json_file_obj)
            if (
                json_content.get("study_name") == self._study_name
                and json_content.get("user") == self._user
            ):
                json_files.append(json_file)
        json_files = set(json_files) - set(self._to_delete)
        if not json_files:
            print(
                f"Warning: No JSON files found in {self._directory} for "
                + f"{self._user}, study_name {self._study_name}."
            )
        self._json_files = iter(json_files)
        return self

    def __next__(self):
        # Retrieve the next result
        try:
            json_file = next(self._json_files)
        except StopIteration:
            self._clean()
            raise StopIteration
        else:
            bin_file = json_file.with_suffix(".bin")
            # We parse the result in a try context, which fails if the versions
            # are not compatible. Instead of raising an error, we just continue.
            try:
                with open(json_file, "r") as json_file_obj:
                    json_content = json.load(json_file_obj)
                result = XbState.from_binary(bin_file, raise_version_error=False)
            except Exception as e:
                print(f"Error loading binary file {bin_file}: {e}")
            else:
                if result is None:
                    # Failed because of incompatible versions
                    # TODO: should we print a warning??? Probably yes..
                    return self.__next__()
                particles = result.particles
                self._to_delete.append(json_file)
                return particles, json_content
