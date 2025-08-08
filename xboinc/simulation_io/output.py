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

from .default_tracker import ElementRefData, default_element_classes, get_default_config
from .version import XbVersion, assert_versions


class XbState(xo.Struct):
    _version = XbVersion  # This HAS to be the first field!
    _i_turn = xo.Int64  # Current turn in tracking
    _xsize = xo.Int64  # Needed to have access to the size in C
    _particles = xt.Particles._XoStruct
    _monitors_metadata = xo.Ref(ElementRefData)

    def __init__(self, monitor_line=None, **kwargs):
        """
        Parameters
        ----------
        particles : xpart.Particles
            The particles in their binary state.
        """

        assert_versions()
        kwargs["_version"] = XbVersion()
        particles = kwargs.pop("particles", None)
        if particles is None or not isinstance(particles, xt.Particles):
            raise ValueError("Need to provide `particles` to XbState.")
        kwargs["_particles"] = particles._xobject

        super().__init__(**kwargs)

        if monitor_line is None:
            self._monitors_metadata = ElementRefData()
        elif isinstance(monitor_line, xt.Line):
            self._monitors_metadata = _build_line_metadata(
                monitor_line,
                _buffer=kwargs["_buffer"],
                store_element_names=kwargs.get("store_element_names", True),
            )

        # self._xsize HAS to be set externally in order to perform the
        # appropriate buffer inspections

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
        with filename.open("rb") as fid:
            state_bytes = fid.read()
        buffer_data = xo.ContextCpu().new_buffer(capacity=len(state_bytes))
        buffer_data.buffer[:] = np.frombuffer(state_bytes, dtype=np.int8)
        # Cast to XbVersion to verify versions of xsuite packages
        version_offset = -1
        for field in cls._fields:
            if field.name == "_version":
                version_offset = field.offset
        if version_offset == -1:
            raise ValueError("No xofield `_version` found in XbState!")
        xb_ver = XbVersion._from_buffer(
            buffer=buffer_data, offset=offset + version_offset
        )
        if not xb_ver.assert_version(
            raise_error=raise_version_error, filename=filename
        ):
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
        assert (
            self._offset == 0
        )  # TODO: create new buffer if this is not the case (like when XbState inside XbInput)
        filename = Path(filename).expanduser().resolve()
        with filename.open("wb") as fid:
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

    @property
    def monitors(self):
        elements = [
            el._DressingClass(_xobject=el) for el in self._monitors_metadata.elements
        ]
        names = self._monitors_metadata.names
        if len(np.array(names)) == 0:
            # line is empty, return empty Line
            return xt.Line(elements=[], element_names=[])
        if len(names) == 0:
            n = len(elements)
            digits = int(np.ceil(np.log10(n)))
            names = [f"el_{i:>0{digits}}" for i in range(n)]
        return xt.Line(elements=elements, element_names=names)


def _check_config(line):
    # Check that the present config is on Xboinc
    default_config_hash = get_default_config()
    for key, val in default_config_hash:
        if key not in line.config:
            print(
                f"Warning: Configuration option `{key}` not found in line.config! "
                + f"Set to Xboinc default `{val}`."
            )
        elif val != line.config[key]:
            print(
                f"Warning: Configuration option `{key}` set to `{line.config[key]}` "
                + f"in line.config! Not supported by Xboinc. Overwritten to default `{val}`."
            )
    for key in set(line.config.keys()) - {k[0] for k in default_config_hash}:
        print(
            f"Warning: Configuration option `{key}` requested in line.config!"
            + "Not supported by Xboinc. Ignored."
        )


def _check_compatible_elements(line):
    # Check that all elements are supported by Xboinc
    default_elements = [d.__name__ for d in default_element_classes]
    for ee in np.unique([ee.__class__.__name__ for ee in line.elements]):
        if ee not in default_elements:
            raise ValueError(
                f"Element of type {ee} not supported " + f"in this version of xboinc!"
            )


def _build_line_metadata(line, _buffer=None, store_element_names=True):
    # Create the ElementRefData from a given line
    line_id = id(line)
    # TODO: caching currently doesn't work
    _previous_line_cache = {}
    if line_id not in _previous_line_cache:
        _check_config(line)
        _check_compatible_elements(line)
        if _buffer is None:
            _buffer = _xboinc_context.new_buffer()
        names = list(line.element_names) if store_element_names else []
        element_ref_data = ElementRefData(
            elements=len(line.element_names),
            names=names,
            _buffer=_buffer,
        )
        element_ref_data.elements = [
            line.element_dict[name]._xobject for name in line.element_names
        ]
        _previous_line_cache[line_id] = element_ref_data

    return _previous_line_cache[line_id]
