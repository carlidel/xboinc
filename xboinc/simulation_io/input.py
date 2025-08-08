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

from .default_tracker import ElementRefData
from .output import XbState, _build_line_metadata
from .version import XbVersion, assert_versions

# TODO: line.particle_ref is not dumped nor retrieved... Why is this no issue?
# TODO: parity
# TODO: can we cache the view on line?

# TODO: Caching does not work as moving elements to buffer does not work correctly
#       Can we cache by making the line_metadata in one buffer which we then always merge to a new one?
#       Input creation should be faster than it is now (~4s)
# The build time of the input file is largely dominated by the rebuilding of the
# ElementRefData. For this reason we cache the line, such that when submitting
# many jobs on the same line only the first job creation takes some time.
_previous_line_cache = {}

_xboinc_context = xo.ContextCpu()


class XbInput(xo.Struct):
    _version = XbVersion  # This HAS to be the first field!
    num_turns = xo.Int64
    num_elements = xo.Int64
    ele_start = xo.Int64  # The start index of the elements in the line
    ele_stop = xo.Int64  # The end index of the elements in the line
    checkpoint_every = xo.Int64
    num_monitors = xo.Int64  # Number of monitors in the line
    idx_monitors = xo.Ref(xo.Int64[:])  # Indices of the monitors in the line
    size_monitors = xo.Ref(xo.Int64[:])  # Buffer size of the monitors
    line_metadata = xo.Ref(ElementRefData)
    xb_state = xo.Ref(XbState) # This HAS to be the last field!

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        particles : xpart.Particles
            The particles to be tracked.
        xb_state : XbState
            The state of the particles. Use either this parameter or
            particles, not both.
        line : xtrack.Line
            The line to be tracked.
        line_metadata : ElementRefData
            Currently not supported (need to fix bug in xobjects).
        num_turns : Int64
            The number of turns to track
        ele_start : Int64 or str, optional
            The start index or name in the line to track from. Defaults to 0.
        ele_stop : Int64 or str, optional
            The end index or name in the line to track to. Defaults to the
            end of the line.
        checkpoint_every : Int64, optional
            When to checkpoint. The default value -1 represents no
            checkpointing.
        store_element_names : bool, optional
            Whether or not to store the element names in the binary.
            Defaults to True.

        The other xofields are generated automatically and will be
        overwritten if provided.
        """
        assert_versions()

        # NOTE: In this initialization, it is important to maintain the order of
        # the fields and of their initialization, as this will affect directly
        # their position in the resulting buffer we operate with. At the end of
        # this initialization, the XbState and its internal monitors-only line
        # will be at the end of the buffer, enabling a simple cut-and-paste
        # manouver at the C++ level in the final Xboinc executable.

        # Set up version and buffer
        kwargs["_version"] = XbVersion()
        kwargs.setdefault("_buffer", _xboinc_context.new_buffer())
        kwargs.setdefault("checkpoint_every", -1)

        # Handle element start/stop positions
        kwargs.setdefault("ele_start", 0)
        kwargs.setdefault("ele_stop", -1)  # -1 means end of line

        line = kwargs.pop("line", None)
        if not isinstance(line, xt.Line):
            raise ValueError("Must provide a valid `line` to XbInput.")

        # Convert element name to index if needed
        if isinstance(kwargs["ele_start"], str):
            kwargs["ele_start"] = line.element_names.index(kwargs["ele_start"])
        if isinstance(kwargs["ele_stop"], str):
            kwargs["ele_stop"] = line.element_names.index(kwargs["ele_stop"])

        # Validate line metadata handling
        if kwargs.pop("line_metadata", None) is not None:
            raise ValueError("Cannot provide the line metadata directly!")
        store_element_names = kwargs.pop("store_element_names", True)

        # Process monitors data
        monitor_indices = []
        monitor_sizes = []
        monitor_line = xt.Line()

        for name, element in line.element_dict.items():
            if str(type(element)).startswith("<class 'xtrack.monitors.particles_monitor."):
                monitor_line.append(name, element)
                monitor_indices.append(line.element_names.index(name))
                monitor_sizes.append(element._xobject._size)

        kwargs["num_monitors"] = len(monitor_indices)
        kwargs["idx_monitors"] = np.array(monitor_indices, dtype=np.int64)
        kwargs["size_monitors"] = np.array(monitor_sizes, dtype=np.int64)

        # Initialize the parent class
        super().__init__(**kwargs)

        # Handle particles or state
        particles = kwargs.pop("particles", None)
        xb_state = kwargs.get("xb_state", None)

        if particles is not None and xb_state is not None:
            raise ValueError("Use either `xb_state` or `particles`, not both.")

        # Set up line metadata
        self.line_metadata = _build_line_metadata(
            line, 
            _buffer=self._buffer, 
            store_element_names=store_element_names
        )
        self.num_elements = len(line.elements)

        if particles is not None:
            self.xb_state = XbState(
                particles=particles,
                monitor_line=monitor_line,
                _i_turn=0,
                _buffer=self._buffer,
                store_element_names=store_element_names,
            )
        elif not isinstance(xb_state, XbState):
            raise ValueError("Need to provide either `xb_state` or `particles`.")

        # Handle element start position
        if hasattr(particles, 'start_tracking_at_element') and particles.start_tracking_at_element >= 0:
            if self.ele_start != 0:
                raise ValueError(
                    "Both ele_start argument and particles.start_tracking_at_element are set. "
                    "Please use only one method."
                )
            self.ele_start = particles.start_tracking_at_element

        # Ensure valid element positions
        self.ele_start = max(0, self.ele_start)
        assert 0 <= self.ele_start <= self.num_elements
        assert self.num_turns > 0

        # Handle element stop position
        if self.ele_stop == -1:
            self.ele_stop = self.num_elements
        else:
            assert 0 <= self.ele_stop <= self.num_elements
            if self.ele_stop <= self.ele_start:
                # Correct for overflow - need extra turn
                self.num_turns += 1

        # Final steps, shrink the buffer
        _shrink(self._buffer)

        # Then, check where the xb_state starts in the buffer, and
        # consequently evaluate its size, necessary for C++ manipulations
        self.xb_state._xsize = self._buffer.capacity - self.xb_state._offset

    @classmethod
    def from_binary(cls, filename, offset=0, raise_version_error=True):
        """
        Create an XbInput from a binary file. The file should not
        contain anything else (otherwise the offset will be wrong).

        Parameters
        ----------
        filename : pathlib.Path
            The binary containing the simulation state.

        Returns
        -------
        XbInput
        """

        # Read binary
        filename = Path(filename)
        with filename.open("rb") as fid:
            state_bytes = fid.read()
        buffer_data = _xboinc_context.new_buffer(capacity=len(state_bytes))
        buffer_data.buffer[:] = np.frombuffer(state_bytes, dtype=np.int8)
        # Cast to XbVersion to verify versions of xsuite packages
        version_offset = -1
        for field in cls._fields:
            if field.name == "_version":
                version_offset = field.offset
        if version_offset == -1:
            raise ValueError("No xofield `_version` found in XbInput!")
        xb_ver = XbVersion._from_buffer(
            buffer=buffer_data, offset=offset + version_offset
        )
        if not xb_ver.assert_version(
            raise_error=raise_version_error, filename=filename
        ):
            return None
        # Retrieve simulation input
        return cls._from_buffer(buffer=buffer_data, offset=offset)

    def to_binary(self, filename):
        """
        Dump the XbInput to a binary file.

        Parameters
        ----------
        filename : pathlib.Path
            The binary containing the simulation state.

        Returns
        -------
        None.
        """
        _shrink(self._buffer)
        assert self._offset == 0
        filename = Path(filename).expanduser().resolve()
        with filename.open("wb") as fid:
            fid.write(self._buffer.buffer.tobytes())

    @property
    def version(self):
        return self._version

    @property
    def line(self):
        elements = [
            el._DressingClass(_xobject=el) for el in self.line_metadata.elements
        ]
        names = self.line_metadata.names
        if len(names) == 0:
            n = len(elements)
            digits = int(np.ceil(np.log10(n)))
            names = [f"el_{i:>0{digits}}" for i in range(n)]
        return xt.Line(elements=elements, element_names=names)

    @line.setter
    def line(self, val):
        # Only works as long as line_metadata is an xo.Ref, but we try to avoid this
        raise NotImplementedError("Setting line metadata is not supported yet.")

    @property
    def particles(self):
        return self.xb_state.particles


def _shrink(buffer):
    # Shrink a buffer by removing all free capacity
    if buffer.get_free() > 0:
        new_capacity = buffer.capacity - buffer.get_free()
        newbuff = buffer._new_buffer(new_capacity)
        buffer.copy_to_native(
            dest=newbuff, dest_offset=0, source_offset=0, nbytes=new_capacity
        )
        buffer.buffer = newbuff
        buffer.capacity = new_capacity
        buffer.chunks = []
