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

import xtrack as xt
import xfields as xf
import xcoll as xc

from xtrack.beam_elements import *
from xtrack.monitors import *
from xtrack.random import *
from xtrack.multisetter import MultiSetter

from .version import assert_versions

ONLY_XTRACK_ELEMENTS = [
    Drift,
    Multipole,
    Bend,
    RBend,
    Quadrupole,
    Sextupole,
    Octupole,
    Magnet,
    SecondOrderTaylorMap,
    Marker,
    ReferenceEnergyIncrease,
    Cavity,
    Elens,
    Wire,
    Solenoid,
    RFMultipole,
    DipoleEdge,
    MultipoleEdge,
    SimpleThinBend,
    SimpleThinQuadrupole,
    LineSegmentMap,
    FirstOrderTaylorMap,
    NonLinearLens,
    # Slices
    DriftSlice,
    DriftSliceBend,
    DriftSliceRBend,
    DriftSliceOctupole,
    DriftSliceQuadrupole,
    DriftSliceSextupole,
    ThickSliceBend,
    ThickSliceRBend,
    ThickSliceOctupole,
    ThickSliceQuadrupole,
    ThickSliceSextupole,
    ThickSliceSolenoid,
    ThinSliceBend,
    ThinSliceRBend,
    ThinSliceBendEntry,
    ThinSliceBendExit,
    ThinSliceRBendEntry,
    ThinSliceRBendExit,
    ThinSliceQuadrupoleEntry,
    ThinSliceQuadrupoleExit,
    ThinSliceSextupoleEntry,
    ThinSliceSextupoleExit,
    ThinSliceOctupoleEntry,
    ThinSliceOctupoleExit,
    ThinSliceOctupole,
    ThinSliceQuadrupole,
    ThinSliceSextupole,
    # Transformations
    XYShift,
    ZetaShift,
    XRotation,
    SRotation,
    YRotation,
    # Apertures
    LimitEllipse,
    LimitRectEllipse,
    LimitRect,
    LimitRacetrack,
    LimitPolygon,
    LongitudinalLimitRect,
    # Monitors
    BeamPositionMonitor,
    BeamSizeMonitor,
    BeamProfileMonitor,
    LastTurnsMonitor,
    ParticlesMonitor,
]

NO_SYNRAD_ELEMENTS = [
    Exciter,
]

# Xfields elements
DEFAULT_XF_ELEMENTS = [
    xf.BeamBeamBiGaussian2D,
    xf.BeamBeamBiGaussian3D,
    xf.SpaceChargeBiGaussian,
]

# Xcoll elements
DEFAULT_XCOLL_ELEMENTS = [
    # ZetaShift,
    xc.BlackAbsorber,
    xc.EverestBlock,
    xc.EverestCollimator,
    xc.EverestCrystal,
    xc.BlowUp,
    xc.EmittanceMonitor,
]

NON_TRACKING_ELEMENTS = [
    RandomUniform,
    RandomExponential,
    RandomNormal,
    RandomRutherford,
    MultiSetter,
]

default_element_classes = (
    ONLY_XTRACK_ELEMENTS
    + NO_SYNRAD_ELEMENTS
    + DEFAULT_XF_ELEMENTS
    + DEFAULT_XCOLL_ELEMENTS
)

# The class ElementRefData is dynamically generated inside the tracker. We
# extract it here and use it to create the line metadata inside XbInput
ElementRefData = xt.tracker._element_ref_data_class_from_element_classes(
    ONLY_XTRACK_ELEMENTS
    + NO_SYNRAD_ELEMENTS
    + DEFAULT_XF_ELEMENTS
    + DEFAULT_XCOLL_ELEMENTS,
)
if {f.name for f in ElementRefData._fields} != {'elements', 'names'}:
    raise RuntimeError("The definition of `ElementRefData` has changed inside Xtrack! "
                     + "This renders Xboinc incompatible. Please ask a dev to update Xboinc.")


_default_tracker_cache = {}


def get_default_tracker():
    """
    Returns the default tracker used by Xboinc.
    """
    assert_versions()
    if 'tracker' in _default_tracker_cache:
        return _default_tracker_cache['tracker']

    line = xt.Line(elements=[])

    # We build the tracker on an empty line, but without compiling.
    line.build_tracker(compile=False, use_prebuilt_kernels=False)
    # Now we overwrite the TrackerData with our ElementRefData class, based on all elements
    tracker = line.tracker._tracker_data_cache[None]
    tracker._element_ref_data = tracker.build_ref_data(tracker._buffer, ElementRefData)

    _default_tracker_cache['tracker'] = line.tracker
    return line.tracker


def get_default_config():
    """
    Returns the default config used by Xboinc.
    """

    assert_versions()
    if 'config' in _default_tracker_cache:
        return _default_tracker_cache['config']

    default_config_hash = get_default_tracker()._hashable_config()
    _default_tracker_cache['config'] = default_config_hash
    return default_config_hash


def get_default_tracker_kernel():
    """
    Returns the default tracker kernel used by Xboinc.
    """

    assert_versions()
    if 'kernel' in _default_tracker_cache:
        return _default_tracker_cache['kernel']

    # Now we trigger compilation
    get_default_tracker().get_track_kernel_and_data_for_present_config()
    kernel = get_default_tracker().track_kernel[get_default_config()]
    _default_tracker_cache['kernel'] = kernel

    return kernel
