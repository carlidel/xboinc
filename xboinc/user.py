# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

import json
from xaux import FsPath

from .general import _pkg_root


user_data_file = FsPath(_pkg_root / "user_data.json")

if not user_data_file.exists():
    with user_data_file.open("w") as fid:
        json.dump({}, fid)


def list_registered_users():
    """
    Lists the registered users in this xboinc installation.
    """
    with user_data_file.open("r") as fid:
        userdict = json.load(fid)
    for key in userdict:
        yield key


def update_user_data(user, data):
    """
    Update the user data in this xboinc installation.

    Parameters
    ----------
    user : string
        Name of the user.
    data : dict
        User metadata.

    Returns
    -------
    None.
    """

    with user_data_file.open("r") as fid:
        userdict = json.load(fid)
    data.pop("user", None)
    if user in userdict:
        userdict[user].update(data)
    else:
        userdict[user] = data
    with user_data_file.open("w") as fid:
        json.dump(userdict, fid)


def get_user_data(user):
    """
    Retrieve the user data in this xboinc installation.

    Parameters
    ----------
    user : string
        Name of the user.

    Returns
    -------
    data : dict
        User metadata.
    """

    with user_data_file.open("r") as fid:
        userdict = json.load(fid)
    if user not in userdict:
        raise ValueError(f"User {user} not registered!")
    return userdict[user]


def get_directory(user):
    """
    Retrieve the user directory in this xboinc installation.

    Parameters
    ----------
    user : string
        Name of the user.

    Returns
    -------
    directory : xaux.FsPath
        User metadata.
    """
    return FsPath(get_user_data(user)["directory"]).resolve()


def get_domain(user):
    """
    Retrieve the user domain (AFS or EOS) in this xboinc
    installation.

    Parameters
    ----------
    user : string
        Name of the user.

    Returns
    -------
    domain : string
        User domain.
    """
    return get_user_data(user)["domain"]


def remove_user(user):
    """
    Delete a user from this xboinc installation.

    Parameters
    ----------
    user : string
        Name of the user.

    Returns
    -------
    None
    """
    with user_data_file.open("r") as fid:
        userdict = json.load(fid)
    if user in userdict:
        userdict.pop(user)
        with user_data_file.open("w") as fid:
            json.dump(userdict, fid)
