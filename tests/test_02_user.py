# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2024.                 #
########################################### #

from pathlib import Path
import json
import pytest

import xboinc as xb
from xboinc.user import user_data_file, get_directory, get_domain, get_user_data
from xboinc.server import server_account, dropdir
from xboinc.server.paths import _test_afs, _test_eos

register_file       = dropdir / f"register_{server_account}.json"
deregister_file     = dropdir / f"deregister_{server_account}.json"
register_file_dev   = dropdir / f"dev_register_{server_account}.json"
deregister_file_dev = dropdir / f"dev_deregister_{server_account}.json"


def test_register():
    xb.register(server_account, _test_afs)
    assert get_directory(server_account) == _test_afs
    assert (get_directory(server_account) / 'input').exists()
    assert (get_directory(server_account) / 'output').exists()
    assert (get_directory(server_account) / 'input_dev').exists()
    assert (get_directory(server_account) / 'output_dev').exists()
    assert get_domain(server_account) == 'afs'
    assert get_user_data(server_account)['directory'] == _test_afs.as_posix()
    assert get_user_data(server_account)['domain'] == 'afs'
    assert register_file.exists()
    assert not deregister_file.exists()
    with register_file.open('r') as fid:
        userdict = json.load(fid)
    assert userdict['user'] == server_account
    assert userdict['directory'] == _test_afs.as_posix()
    assert userdict['domain'] == 'afs'
    assert register_file_dev.exists()
    assert not deregister_file_dev.exists()
    with register_file_dev.open('r') as fid:
        userdict = json.load(fid)
    assert userdict['user'] == server_account
    assert userdict['directory'] == _test_afs.as_posix()
    assert userdict['domain'] == 'afs'

    with pytest.raises(NotImplementedError):
        xb.register(server_account, _test_eos)


def test_deregister():
    xb.deregister(server_account)
    with user_data_file.open('r') as fid:
        userdict = json.load(fid)
    assert server_account not in userdict.keys()
    with pytest.raises(ValueError):
        get_user_data(server_account)
    assert not register_file.exists()
    assert not register_file_dev.exists()
    assert deregister_file.exists()
    with deregister_file.open('r') as fid:
        userdict = json.load(fid)
    assert userdict['user'] == server_account
    assert deregister_file_dev.exists()
    with deregister_file_dev.open('r') as fid:
        userdict = json.load(fid)
    assert userdict['user'] == server_account
