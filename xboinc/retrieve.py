# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

import json

import pandas as pd
from tqdm.auto import tqdm
from warnings import warn
from xaux import eos_accessible, FsPath

from .server.tools import untar
from .simulation_io import XbState, assert_versions
from .user import get_directory, get_domain
from .df_wu import query_work_units_by_user


class ResultRetriever:
    """
    Class to retrieve and manage results from Xboinc simulations.
    
    This class provides functionality to retrieve, index, and manage simulation
    results from BOINC work units. It can untar result files, create indexes,
    and provide various views and statistics about completed jobs.
    
    Attributes
    ----------
    _user : str
        The user that submitted the BOINC jobs
    _domain : str
        The domain where results are stored (e.g., 'eos')
    _directory : FsPath
        Path to the directory containing results
    _dev_server : bool
        Whether using development server
    _df : pd.DataFrame
        Indexed DataFrame of all available results
    
    Examples
    --------
    >>> retriever = ResultRetriever('myuser', dev_server=True)
    >>> studies = retriever.get_study_list()
    >>> for job_name, particles in retriever.iterate_results('my_study'):
    ...     # Process particles data
    ...     pass
    """

    def _untar_results(self, path: FsPath, silent: bool = False):
        """
        Untar all compressed result files in the given path.
        
        Parameters
        ----------
        path : FsPath
            Directory path containing .tar.gz files to extract
        silent : bool, optional
            If True, suppress progress bar output (default: False)
        """
        for tar_file in tqdm(
            path.glob("*.tar.gz"), desc="Untarring results", disable=silent
        ):
            untar(tar_file)

    def _index_results(self, path: FsPath, silent: bool = False) -> pd.DataFrame:
        """
        Index all result files in the given path and create a DataFrame.
        
        Scans for .bin files in subdirectories and extracts metadata from
        filenames to create a structured index of available results.
        
        Parameters
        ----------
        path : FsPath
            Directory path to scan for result files
        silent : bool, optional
            If True, suppress progress bar output (default: False)
            
        Returns
        -------
        pd.DataFrame
            DataFrame with columns: user, study_name, job_name, wu_name, bin_file
            Each row represents one available result file
        """
        df = pd.DataFrame(
            columns=["user", "study_name", "job_name", "wu_name", "bin_file"]
        )

        # iterate all folders in the path
        for folder in tqdm(path.glob("*/"), desc="Indexing results", disable=silent):
            if not folder.is_dir():
                continue
            # iterate all result bin files in the folder
            for bin_file in folder.glob("*.bin"):
                # extract user, study_name, and job_name from the bin file name
                parts = bin_file.name.split("__")
                if len(parts) < 3:
                    continue
                user = parts[0]
                study_name = parts[1]
                job_name = "__".join(parts[2])
                wu_name = bin_file.name.replace(".bin", "")
                # append to the DataFrame
                df = df.append(
                    {
                        "user": user,
                        "study_name": study_name,
                        "job_name": job_name,
                        "wu_name": wu_name,
                        "bin_file": bin_file,
                    },
                    ignore_index=True,
                )
        return df

    def __init__(self, user, dev_server=False, silent=False):
        """
        Initialize the ResultRetriever for a specific user.
        
        Parameters
        ----------
        user : str
            The user that submitted to BOINC. User should be member of the 
            CERN xboinc-submitters egroup with proper permissions.
        dev_server : bool, optional
            Whether to retrieve from the development server (default: False)
        silent : bool, optional
            Whether to suppress output messages and progress bars (default: False)
            
        Raises
        ------
        NotImplementedError
            If dev_server=False (regular server not yet operational)
        ConnectionError
            If EOS is not accessible when domain is 'eos'
            
        Examples
        --------
        >>> retriever = ResultRetriever('myuser', dev_server=True, silent=True)
        >>> overview = retriever.get_overview()
        """

        if not dev_server:
            raise NotImplementedError(
                "Regular server not yet operational. " + "Please use dev_server=True."
            )
        assert_versions()
        self._user = user
        self._domain = get_domain(user)
        if self._domain == "eos":
            if not eos_accessible:
                raise ConnectionError(
                    "EOS is not accessible! Please check your connection."
                )
        if dev_server:
            self._directory = get_directory(user) / "output_dev"
        else:
            self._directory = get_directory(user) / "output"

        self._dev_server = dev_server
        self._to_delete = []

        self._untar_results(self._directory, silent=silent)
        self._df = self._index_results(self._directory, silent=silent)

    def get_overview(self):
        """
        Get a comprehensive overview of all available results.
        
        Returns
        -------
        pd.DataFrame
            DataFrame containing all indexed results with columns:
            user, study_name, job_name, wu_name, bin_file
        """
        return self._df

    def get_study_list(self):
        """
        Get a list of all unique study names in the available results.
        
        Returns
        -------
        list of str
            Sorted list of unique study names found in the results
        """
        return self._df["study_name"].unique().tolist()

    def get_study_status(self, study_name, verbose=False):
        """
        Get detailed status information for a specific study.
        
        Compares local results with server work units to provide comprehensive
        status information including completion rates and missing jobs.
        
        Parameters
        ----------
        study_name : str
            Name of the study to check status for
        verbose : bool, optional
            If True, print detailed job lists (default: False)
            
        Returns
        -------
        tuple of (list, set)
            - list: Job names available in results
            - set: Job names missing from results but present on server
            
        Raises
        ------
        ValueError
            If study_name is not found in results or server work units
            
        Warnings
        --------
        UserWarning
            If there are mismatches between local results and server status
        """
        # Is the study name valid?
        if study_name not in self._df["study_name"].unique():
            raise ValueError(f"Study name {study_name} not found in results.")
        # Get server dataframe
        server_df = query_work_units_by_user(self._user, dev_server=self._dev_server)
        if study_name not in server_df["study_name"].unique():
            raise ValueError(f"Study name {study_name} not found in server work units.")
        result_job_names = self._df[self._df["study_name"] == study_name][
            "job_name"
        ].to_list()
        result_job_names.sort()
        remote_job_names = server_df[server_df["study_name"] == study_name][
            "job_name"
        ].to_list()
        remote_job_names.sort()
        completed_remote_job_names = server_df[
            (server_df["study_name"] == study_name)
            & (server_df["status"] == "completed")
        ]["job_name"].to_list()
        completed_remote_job_names.sort()

        # Check 1: result_job_names should be equal to completed_remote_job_names
        if result_job_names != completed_remote_job_names:
            warn(
                f"Warning: The job names in the results ({result_job_names}) "
                f"do not match the completed job names on the server!"
                "This might indicate that some results were deleted or not retrieved correctly."
                "Please contact the Xboinc team if you think this is an error.",
                UserWarning,
            )
        # Check 2: remote_job_names should contain all job names in the results
        if not all(job in remote_job_names for job in result_job_names):
            warn(
                f"Warning: The job names in the results ({result_job_names}) "
                f"are not all present in the remote server job names ({remote_job_names}). "
                "This might indicate that some jobs were not submitted correctly or were deleted.",
                UserWarning,
            )
        diff_jobs = set(remote_job_names) - set(result_job_names)
        err_jobs = result_job_names - diff_jobs
        # Print statistics
        print(f"Study: {study_name}")
        print(f"Total jobs in results: {len(result_job_names)}")
        print(f"Total jobs on server: {len(remote_job_names)}")
        print(
            f"Percentage of jobs completed: {(len(completed_remote_job_names) / len(result_job_names)) * 100:.2f}%"
        )

        if verbose:
            print("Results available by job name:")
            for job_name in result_job_names:
                print(f"{job_name}", end=", ")
            print("\n")
            if diff_jobs:
                print("Results not available by job name:")
                for job_name in diff_jobs:
                    print(f"{job_name}", end=", ")
                print("\n")
            if err_jobs:
                print(
                    "WARNING: The following jobs do not match the remote server job names:"
                )
                for job_name in err_jobs:
                    print(f"{job_name}", end=", ")
                print("\n")

        return result_job_names, diff_jobs

    def iterate_results(self, study_name):
        """
        Iterate over all results for a specific study.
        
        Yields tuples of job names and their corresponding particle data
        for all completed jobs in the specified study.
        
        Parameters
        ----------
        study_name : str
            Name of the study to iterate over
            
        Yields
        ------
        tuple of (str, xpart.Particles)
            Job name and corresponding particles object for each result
            
        Raises
        ------
        ValueError
            If study_name is not found in available results
            
        Warnings
        --------
        UserWarning
            If a binary file is incompatible with current Xboinc version
            
        Examples
        --------
        >>> retriever = ResultRetriever('myuser', dev_server=True)
        >>> for job_name, particles in retriever.iterate_results('my_study'):
        ...     print(f"Processing job: {job_name}")
        ...     print(f"Number of particles: {len(particles.x)}")
        """
        if study_name not in self._df["study_name"].unique():
            raise ValueError(f"Study name {study_name} not found in results.")
        for row in self._df[self._df["study_name"] == study_name].itertuples():
            job_name = row.job_name
            bin_file = row.bin_file
            result = XbState.from_binary(bin_file, raise_version_error=False)
            if result is None:
                warn(
                    f"Warning: The binary file {bin_file} is not compatible with the current Xboinc version. "
                    "Skipping this result.",
                    UserWarning,
                )
                continue
            yield job_name, result.particles

    def clean(self, study_name):
        """
        Clean up results for a specific study.
        
        Removes all binary result files, empty directories, and clears
        the study from the internal DataFrame index.
        
        Parameters
        ----------
        study_name : str
            Name of the study to clean up
            
        Raises
        ------
        ValueError
            If study_name is not found in available results
            
        Warning
        -------
        This operation is irreversible. All result files for the study
        will be permanently deleted.
        """
        if study_name not in self._df["study_name"].unique():
            raise ValueError(f"Study name {study_name} not found in results.")
        for row in self._df[self._df["study_name"] == study_name].itertuples():
            bin_file = row.bin_file
            if bin_file.exists():
                bin_file.unlink()
        # Remove empty directories
        for folder in self._directory.glob("*/"):
            if not any(folder.iterdir()):
                folder.rmdir()
        # Clear the DataFrame
        self._df = self._df[self._df["study_name"] != study_name]
        print(f"Cleaned up results for study {study_name}!")

    @classmethod
    def iterate(cls, user, study_name, dev_server=False, silent=True):
        """
        Class method to directly iterate over results for a user and study.
        
        Convenient method that creates a ResultRetriever instance and immediately
        starts iterating over results without requiring explicit instantiation.
        
        Parameters
        ----------
        user : str
            The user that submitted the BOINC jobs
        study_name : str
            Name of the study to iterate over
        dev_server : bool, optional
            Whether to use development server (default: False)
        silent : bool, optional
            Whether to suppress output messages (default: True)
            
        Yields
        ------
        tuple of (str, xpart.Particles)
            Job name and corresponding particles object for each result
            
        Examples
        --------
        >>> for job_name, particles in ResultRetriever.iterate('myuser', 'my_study', dev_server=True):
        ...     # Process particles data
        ...     pass
        """
        instance = cls(user, dev_server=dev_server, silent=silent)
        return instance.iterate_results(study_name)

    @classmethod
    def overview(cls, user, dev_server=False, silent=True):
        """
        Class method to get an overview of results for a specific user.
        
        Parameters
        ----------
        user : str
            The user that submitted the BOINC jobs
        dev_server : bool, optional
            Whether to use development server (default: False)
        silent : bool, optional
            Whether to suppress output messages (default: True)
            
        Returns
        -------
        pd.DataFrame
            DataFrame with overview of all available results
            
        Examples
        --------
        >>> overview_df = ResultRetriever.overview('myuser', dev_server=True)
        >>> print(overview_df.groupby('study_name').size())
        """
        instance = cls(user, dev_server=dev_server, silent=silent)
        return instance.get_overview()

    @classmethod
    def status(cls, user, study_name, dev_server=False, silent=True, verbose=False):
        """
        Class method to get status of results for a specific user and study.
        
        Parameters
        ----------
        user : str
            The user that submitted the BOINC jobs
        study_name : str
            Name of the study to check status for
        dev_server : bool, optional
            Whether to use development server (default: False)
        silent : bool, optional
            Whether to suppress output messages (default: True)
        verbose : bool, optional
            If True, print detailed job lists (default: False)
            
        Returns
        -------
        tuple of (list, set)
            - list: Job names available in results
            - set: Job names missing from results but present on server
            
        Examples
        --------
        >>> available, missing = ResultRetriever.status('myuser', 'my_study', dev_server=True)
        >>> print(f"Available jobs: {len(available)}, Missing jobs: {len(missing)}")
        """
        instance = cls(user, dev_server=dev_server, silent=silent)
        return instance.get_study_status(study_name=study_name, verbose=verbose)
