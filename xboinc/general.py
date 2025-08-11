# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

from pathlib import Path

_pkg_root = Path(__file__).parent.absolute()


# ==============================================================================
# Do not change
# ==============================================================================

__version__ = '0.4.1'

# These are the xsuite modules that are used by boinc and the versions they are
# tied to. This will be automatically updated from the active environment when
# making a minor release. If a new package needs to be pinned, add it here with
# a random version number, and similarily in the pyproject.toml
__xsuite__versions__ = {
    'xobjects' : '0.5.0',
    'xdeps'    : '0.10.5',
    'xpart'    : '0.23.0',
    'xtrack'   : '0.84.7',
    'xfields'  : '0.24.0',
    'xcoll'    : '0.6.1',
    'xaux'     : '0.3.5',
}
# ==============================================================================
