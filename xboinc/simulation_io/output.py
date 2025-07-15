# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

# ==============================================================================
# IMPORTANT
# ==============================================================================
# Only make changes to this file just before a minor version bump (need a
# separate commit though) to avoid having multiple xboinc versions with
# out-of-sync executables.
# ==============================================================================


from pathlib import Path

import numpy as np
import xobjects as xo
import xtrack as xt

from .version import XbVersion, assert_versions


class XbState(xo.Struct):
    _version   = XbVersion     # This HAS to be the first field!
    _i_turn    = xo.Int64      # Current turn in tracking (not necessarily the same as particles.at_turn)
    _xsize     = xo.Int64      # Needed to have access to the size in C
    _particles = xt.Particles._XoStruct

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        particles : xpart.Particles
            The particles in their binary state.
        """

        assert_versions()
        kwargs['_version'] = XbVersion()
        particles = kwargs.pop('particles', None)
        if particles is None or not isinstance(particles, xt.Particles):
            raise ValueError("Need to provide `particles` to XbState.")
        kwargs['_particles'] = particles._xobject
        super().__init__(**kwargs)
        self._xsize = self._size


    @classmethod
    def from_binary(cls, filename, offset=0, raise_version_error=True):
        """
        Create an XbState from a binary file. The file should not
        contain anything else (otherwise the offset will be wrong).

        Parameters
        ----------
        filename : pathlib.Path
            The binary containing the simulation state.

        Returns
        -------
        XbState
        """

        # Read binary
        filename = Path(filename)
        with filename.open('rb') as fid:
            state_bytes = fid.read()
        buffer_data = xo.ContextCpu().new_buffer(capacity=len(state_bytes))
        buffer_data.buffer[:] = np.frombuffer(state_bytes, dtype=np.int8)
        # Cast to XbVersion to verify versions of xsuite packages
        version_offset = -1
        for field in cls._fields:
            if field.name == '_version':
                version_offset = field.offset
        if version_offset == -1:
            raise ValueError("No xofield `_version` found in XbState!")
        xb_ver = XbVersion._from_buffer(buffer=buffer_data, offset=offset+version_offset)
        if not xb_ver.assert_version(raise_error=raise_version_error, filename=filename):
            return None
        # Retrieve simulation state
        return cls._from_buffer(buffer=buffer_data, offset=offset)

    def to_binary(self, filename):
        """
        Dump the XbState to a binary file.

        Parameters
        ----------
        filename : pathlib.Path
            The binary containing the simulation state.

        Returns
        -------
        None.
        """
        assert self._offset == 0     # TODO: create new buffer if this is not the case (like when XbState inside XbInput)
        filename = Path(filename).expanduser().resolve()
        with filename.open('wb') as fid:
            fid.write(self._buffer.buffer.tobytes())


    @property
    def version(self):
        return self._version

    @property
    def particles(self):
        return xt.Particles(_xobject=self._particles)

    @property
    def i_turn(self):
        return self._i_turn
