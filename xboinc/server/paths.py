# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

from xaux import FsPath

afsusr = FsPath('/afs/cern.ch/user/s/sixtadm')
eosusr = FsPath('/eos/user/s/sixtadm')

eosdir    = eosusr / 'xboinc_server' # EOS spooldir for server
dropdir   = eosdir / 'drop'          # only location where users have write access (i.e. to register)
infowudir = eosdir / "info"          # location of work units info database

