# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

from pathlib import Path

afsusr  = Path('/afs/cern.ch/user/s/sixtadm')
eosusr  = Path('/eos/user/s/sixtadm')

eosdir     = eosusr / 'xboinc_server'         # EOS spooldir for server
dropdir    = eosdir / 'drop'                  # only location where users have write access (i.e. to register)
infowudir = eosdir / "info"                   # location of work units info database


_test_afs = afsusr / 'public' / 'test_xboinc'
_test_eos = eosusr / 'test_xboinc'
