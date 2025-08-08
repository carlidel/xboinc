// copyright ############################### #
// This file is part of the Xboinc Package.  #
// Copyright (c) CERN, 2025.                 #
// ######################################### #

// This file specifies the version of the Xboinc executable.

#ifndef XB_EXECUTABLE_VERSION_H
#define XB_EXECUTABLE_VERSION_H

// ===============================================================================================
// IMPORTANT
// ===============================================================================================
// Only make changes to this file just before a minor version bump (need a separate commit though)
// to avoid having multiple xboinc versions with out-of-sync executables.
// ===============================================================================================

// =============================================================================
// Do not change
// =============================================================================
// version XXX.YYY as int  (no patch)
const int64_t xboinc_exec_version = 5;
// =============================================================================

#endif /* XB_EXECUTABLE_VERSION_H */