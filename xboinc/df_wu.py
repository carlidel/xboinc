# copyright ###################################### #
# This file is part of the Xboinc Package.         #
# Copyright (c) CERN, 2025.                        #
# ################################################ #

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import pandas as pd

from xaux import FsPath, timestamp

from .server.paths import infowudir
from .user import list_registered_users

wu_db = infowudir / "wu_status.db"
wu_db_dev = infowudir / "wu_status_dev.db"


def _get_read_only_wu_db_connection(dev_server: bool = False) -> sqlite3.Connection:
    """Get a read-only database connection."""
    conn = sqlite3.connect(f"file:{wu_db_dev if dev_server else wu_db}?mode=ro", uri=True)
    return conn


###################### Getters #################################################


def query_all_work_units(dev_server=False) -> pd.DataFrame:
    """List all work units in the database as a Pandas DataFrame."""
    with _get_read_only_wu_db_connection(dev_server) as conn:
        df = pd.read_sql_query("SELECT * FROM wu_status", conn)
        return df


def query_work_units_by_user(user: str, dev_server=False) -> pd.DataFrame:
    """List all work units for a specific user as a Pandas DataFrame."""
    with _get_read_only_wu_db_connection(dev_server) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM wu_status WHERE user=?", conn, params=(user,)
        )
        return df


def query_work_units_by_status(status: str, dev_server=False) -> pd.DataFrame:
    """List all work units with a specific status as a Pandas DataFrame."""
    with _get_read_only_wu_db_connection(dev_server) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM wu_status WHERE status=? AND dev_server=?",
            conn,
            params=(status, dev_server),
        )
        return df


def query_registered_work_units(
    status: Optional[str] = None, dev_server: bool = False
) -> pd.DataFrame:
    """
    List all work units for the registered users with an optional status filter.

    Parameters
    ----------
    status : Optional[str]
        The status to filter work units (e.g., 'running', 'completed').
    dev_server : bool
        Whether to query for the development server or production server.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the work units for the user.
    """
    all_df = None
    for i, user in enumerate(list_registered_users()):
        if status:
            df = query_work_units_by_status(status, dev_server)
            df = df[df["user"] == user]
        else:
            df = query_work_units_by_user(user, dev_server)
        if i == 0:
            all_df = df
        else:
            all_df = pd.concat([all_df, df], ignore_index=True)
    return all_df
