# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

import os
import platform
import shutil
import subprocess
from pathlib import Path

import xobjects as xo
import xtrack as xt

from ..general import _pkg_root
from ..simulation_io import (
    XbInput,
    XbState,
    XbVersion,
    app_version,
    assert_versions,
    get_default_tracker_kernel,
)

# ===============================================================================================
# IMPORTANT
# ===============================================================================================
# Only make changes to this file just before a minor version bump (need a separate commit though)
# to avoid having multiple xboinc versions with out-of-sync executables.
# ===============================================================================================

insert_in_all_files = """
#include <stdio.h>
#ifndef NULL
    #define NULL 0
#endif
"""

_sources = [
    Path.cwd() / f for f in ["main.c", "Makefile", "xtrack.c", "xtrack.h", "version.h"]
]


def generate_executable_source(*, overwrite=False, _context=None):
    """
    Generate all source files needed to compile the Xboinc executable.

    Parameters
    ----------
    overwrite : bool, optional
        Whether or not to overwrite existing source files.

    Returns
    -------
    None
    """

    assert _context is None
    assert_versions()

    if not (Path.cwd() / "xb_input.h").exists() or overwrite:
        # The XbInput source API should not be static, as it has to be exposed to main.
        # TODO: Do we still want to inline this? If yes, we need to adapt xo.specialize_source
        #       to pass the replacement of /*gpufun*/ as an option
        conf = xo.typeutils.default_conf.copy()
        conf["gpufun"] = ""
        xb_input_sources = [
            insert_in_all_files,
            xo.specialize_source(
                XbVersion._gen_c_api(conf).source, specialize_for="cpu_serial"
            ),
            xo.specialize_source(
                XbState._gen_c_api(conf).source, specialize_for="cpu_serial"
            ),
            xo.specialize_source(
                XbInput._gen_c_api(conf).source, specialize_for="cpu_serial"
            ),
        ]
        xb_input_h = "\n".join(xb_input_sources)
        with (Path.cwd() / "xb_input.h").open("w") as fid:
            fid.write(xb_input_h)

    if not (Path.cwd() / "xtrack_tracker.h").exists() or overwrite:
        track_kernel = get_default_tracker_kernel()
        xtrack_tracker_h = insert_in_all_files + track_kernel.specialized_source
        with (Path.cwd() / "xtrack_tracker.h").open("w") as fid:
            fid.write(xtrack_tracker_h)

    for file in _sources:
        if not file.exists() or overwrite:
            shutil.copy(_pkg_root / "executable" / file.name, Path.cwd())


# BOINC executable naming conventions:
# windows_intelx86            Microsoft Windows (98 or later) running on an Intel x86-compatible CPU   (32bit)
# windows_x86_64              Microsoft Windows running on an AMD x86_64 or Intel EM64T CPU
# i686-pc-linux-gnu           Linux running on an Intel x86-compatible CPU    (32bit)
# x86_64-pc-linux-gnu         Linux running on an AMD x86_64 or Intel EM64T CPU
# powerpc-apple-darwin        Mac OS X 10.3 or later running on Motorola PowerPC
# i686-apple-darwin           Mac OS 10.4 or later running on Intel   (32bit)
# x86_64-apple-darwin         Intel 64-bit Mac OS 10.5 or later
# arm64-apple-darwin          Mac OS on M1 or M2
# sparc-sun-solaris2.7        Solaris 2.7 running on a SPARC-compatible CPU
# sparc-sun-solaris           Solaris 2.8 or later running on a SPARC-compatible CPU
# sparc64-sun-solaris         Solaris 2.8 or later running on a SPARC 64-bit CPU
# powerpc64-ps3-linux-gnu     Sony Playstation 3 running Linux
# arm-android-linux-gnu       Android running on ARM
# aarch64-android-linux-gnu   Android running on aarch64
# aarch64-unknown-linux-gnu   Linux running aarch64
# x86_64-pc-freebsd__sse2     Free BSD running on 64 bit X86


def generate_executable(*, keep_source=False, clean=True, boinc_path=None, target=None):
    """
    Generate the Xboinc executable.

    Parameters
    ----------
    keep_source : bool, optional
        Whether or not to keep the source files. Defaults to False.
    clean : bool, optional
        Whether or not to clean the make directory. Defaults to True.
    boinc_path : pathlib.Path, optional
        The path to the local BOINC installation. If none, an executable
        without the BOINC API is generated. Defaults to None.
    target : string, optional
        The target architecture to compile to. Not yet implemented.

    Returns
    -------
    None
    """
    assert target is None
    assert_versions()

    # Check boinc path
    if boinc_path is not None:
        boinc_path = Path(boinc_path).expanduser().resolve()
        if not boinc_path.is_dir() or not boinc_path.exists():
            raise RuntimeError(f"BOINC path {boinc_path} does not exist!")
        boinc_api = boinc_path / "api" / "libboinc_api.a"
        boinc_lib = boinc_path / "lib" / "libboinc.a"
        if not boinc_api.exists():
            raise RuntimeError(f"Cannot find BOINC API {boinc_api}!")
        if not boinc_lib.exists():
            raise RuntimeError(f"Cannot find BOINC LIB {boinc_lib}!")

    config = Path.cwd() / "xb_input.h"
    tracker = Path.cwd() / "xtrack_tracker.h"
    if (
        not config.exists()
        or not tracker.exists()
        or not all([s.exists() for s in _sources])
    ):
        generate_executable_source()

    # Locate xtrack
    xtrack_dir = xt._pkg_root

    # Verify dependencies
    if shutil.which("gcc") is None and shutil.which("clang") is None:
        raise RuntimeError("Neither `gcc` or `clang` are found. Install a C compiler.")
    if shutil.which("g++") is None and shutil.which("clang++") is None:
        raise RuntimeError(
            "Neither `g++` or `clang++` are found. Install a C++ compiler."
        )
    if shutil.which("make") is None:
        raise RuntimeError("Please install `make` before generating the executable.")
    if boinc_path is not None:
        for dep in ["automake", "m4", "libtool", "autoconf", "pkg-config"]:
            if shutil.which(dep) is None:
                raise RuntimeError(
                    f"Please install `{dep}` before generating the executable."
                )
    _check_libstd()

    # Create executable name
    app_tag = f"{app_version}"
    machine = platform.machine().strip().lower() or "none"
    thisos = platform.system().strip().lower() or "none"

    # vendor and thisos post-processing as before
    vendor = "apple" if thisos == "darwin" else "pc"
    thisos = f"{thisos}-gnu" if thisos == "linux" else thisos
    app_tag += f"-{machine}-{vendor}-{thisos}"

    # Compile!
    if target is None:
        try:
            cmd = subprocess.run(
                ["make", "clean"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(e.stdout.decode("UTF-8").strip())
            stderr = e.stderr.decode("UTF-8").strip()
            raise RuntimeError(f"Make clean failed. Stderr:\n {stderr}") from e

        try:
            if boinc_path is None:
                app = "xboinc_test"
                cmd = subprocess.run(
                    ["make", app],
                    env={**os.environ, "XTRACK_PYTHON_DIR": xtrack_dir.as_posix()},
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            else:
                app = "xboinc"
                cmd = subprocess.run(
                    ["make", app],
                    env={
                        **os.environ,
                        "BOINC_DIR": boinc_path.as_posix(),
                        "XTRACK_PYTHON_DIR": xtrack_dir.as_posix(),
                    },
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
        except subprocess.CalledProcessError as e:
            print(e.stdout.decode("UTF-8").strip())
            stderr = e.stderr.decode("UTF-8").strip()
            raise RuntimeError(f"Compilation failed. Stderr:\n {stderr}") from e

        print(cmd.stdout.decode("UTF-8").strip())
        Path(app).rename(f"{app}_{app_tag}")
    else:
        raise NotImplementedError(
            "Target architecture is not yet implemented. Please set target=None."
        )

    # Clean up
    if clean:
        try:
            cmd = subprocess.run(
                ["make", "clean"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(e.stdout.decode("UTF-8").strip())
            stderr = e.stderr.decode("UTF-8").strip()
            raise RuntimeError(f"Could not run `make clean`. Stderr:\n {stderr}") from e

    if not keep_source:
        config.unlink()
        tracker.unlink()
        for s in _sources:
            s.unlink()

    # if windows64:
    #     if shutil.which("x86_64-w64-mingw32-gcc") is not None:
    #         compiler = "x86_64-w64-mingw32-gcc"
    #     else:
    #         raise ValueError("Mingw32 not found!")
    #     tag += '-windows_x86_64.exe'
    # elif windows32:
    #     if shutil.which("i686-w64-mingw32-gcc") is not None:
    #         compiler = "i686-w64-mingw32-gcc"
    #     else:
    #         raise ValueError("Mingw32 not found!")
    #     tag += '-windows_intelx86.exe'
    # else:
    #     if shutil.which("gcc") is not None:
    #         compiler = "gcc"
    #     elif shutil.which("clang") is not None:
    #         compiler = "clang"
    #     else:
    #         raise RuntimeError("Neither clang or gcc are found. Install a C compiler.")


def _check_libstd():
    missing_lib = False
    stderr = None

    try:
        subprocess.run(
            ["make", "libstdc++.a"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("UTF-8").strip().split("\n")
        missing_lib = True
    lib = Path("libstdc++.a")
    if lib.is_symlink():
        try:
            if not lib.exists() or lib.readlink() == lib:
                missing_lib = True
        except PermissionError:
            missing_lib = True
    elif lib.exists():
        raise ValueError(
            "Something is wrong; `libstdc++.a` should be a symlink but is a regular file..."
        )
    else:
        missing_lib = True

    if missing_lib:
        stderr = "" if stderr is None else f"\nStderr:\n {stderr}"
        if lib.exists():
            lib.unlink()
        raise RuntimeError(
            "Make cannot find `libstdc++.a`."
            f"Please install it (e.g. `conda install libstdcxx-ng`).{stderr}"
        )
