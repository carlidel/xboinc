# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

import os
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
    Path.cwd() / f
    for f in ["main.cpp", "CMakeLists.txt", "xtrack.c", "xtrack.h", "version.h"]
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


def generate_executable(
    *, keep_source=False, clean=True, vcpkg_root=None, target_triplet="x64-linux"
):
    """
    Generate the Xboinc executable.

    Parameters
    ----------
    keep_source : bool, optional
        Whether or not to keep the source files. Defaults to False.
    clean : bool, optional
        Whether or not to clean the make directory. Defaults to True.
    vcpkg_root : pathlib.Path, optional
        The path to the local VCPKG installation. If none, an executable
        without the BOINC API is generated. Defaults to None.
    target_triplet : string, optional
        The target architecture to compile to. Currently x64-linux and
        x64-mingw-static (i.e. Windows 64-bit) are supported.
        Defaults to x64-linux.

    Returns
    -------
    None
    """
    assert_versions()

    # Check vcpkg path
    if vcpkg_root is not None:
        vcpkg_root = Path(vcpkg_root).expanduser().resolve()
        if not vcpkg_root.is_dir() or not vcpkg_root.exists():
            raise RuntimeError(f"VCPKG path {vcpkg_root} does not exist!")

    config = Path.cwd() / "xb_input.h"
    tracker = Path.cwd() / "xtrack_tracker.h"
    if (
        not config.exists()
        or not tracker.exists()
        or not all(s.exists() for s in _sources)
    ):
        generate_executable_source()

    # Locate xtrack
    xtrack_dir = xt._pkg_root

    # Create executable name
    app_tag = f"{app_version}"
    # Currently, we only support the x64-linux and x64-mingw-static triplets
    # corresponding, respectively, to x86_64-pc-linux-gnu and windows_x86_64
    if target_triplet == "x64-linux":
        app_tag += "-x86_64-pc-linux-gnu"
    elif target_triplet == "x64-mingw-static":
        app_tag += "-windows_x86_64"
    else:
        raise NotImplementedError(
            f"Target triplet {target_triplet} not supported. "
            "Currently only x64-linux and x64-mingw-static are supported."
        )

    # Compile!
    # 1. create a directory for the build
    build_dir = Path.cwd() / "build"
    if not build_dir.exists():
        build_dir.mkdir(parents=True, exist_ok=True)

    # 2. set the environment variables for cmake
    env_dict = {
        **os.environ,
        "XTRACK_PYTHON_DIR": xtrack_dir.as_posix(),
    }
    cmake_args = [
        f"-DXTRACK_PYTHON_DIR={xtrack_dir.as_posix()}",
        "-DCMAKE_BUILD_TYPE=Release",
    ]

    # add vcpkg root if provided
    if vcpkg_root is not None:
        env_dict["VCPKG_ROOT"] = vcpkg_root.as_posix()
        env_dict["VCPKG_TARGET_TRIPLET"] = target_triplet
        cmake_args.append(f"-DVCPKG_ROOT={vcpkg_root.as_posix()}")
        cmake_args.append(f"-DVCPKG_TARGET_TRIPLET={target_triplet}")
        cmake_args.append(
            f"-DCMAKE_TOOLCHAIN_FILE={vcpkg_root.as_posix()}/scripts/buildsystems/vcpkg.cmake"
        )

    cmake_command = [
        "cmake" if target_triplet != "x64-mingw-static" else "mingw64-cmake",
        "..",
    ] + cmake_args

    # 3. run cmake to configure the build
    try:
        print(f"Running command: {' '.join(cmake_command)}")
        cmd = subprocess.run(
            cmake_command,
            cwd=build_dir,
            env=env_dict,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(e.stdout.decode("UTF-8").strip())
        stderr = e.stderr.decode("UTF-8").strip()
        raise RuntimeError(f"Configuration failed. Stderr:\n {stderr}") from e

    # 4. run make to build the executable
    make_cmd = "make" if target_triplet != "x64-mingw-static" else "mingw64-make"
    app_name = "xboinc_test" if vcpkg_root is None else "xboinc"
    try:
        print(f"Running command: {make_cmd} {app_name}")
        cmd = subprocess.run(
            [make_cmd, app_name],
            cwd=build_dir,
            env=env_dict,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(e.stdout.decode("UTF-8").strip())
        stderr = e.stderr.decode("UTF-8").strip()
        raise RuntimeError(f"Compilation failed. Stderr:\n {stderr}") from e

    # 5. rename the executable
    if target_triplet == "x64-mingw-static":
        # For MinGW, we need to rename the executable to have a .exe extension
        Path(build_dir / (app_name + ".exe")).rename(
            build_dir.parent / f"{app_name}_{app_tag}.exe"
        )
    else:
        Path(build_dir / app_name).rename(build_dir.parent / f"{app_name}_{app_tag}")

    # 6. clean up
    if clean:
        # remove the build directory
        try:
            shutil.rmtree(build_dir)
        except OSError as e:
            raise RuntimeError(
                f"Could not remove build directory {build_dir}. Error: {e}"
            ) from e

    if not keep_source:
        # remove the source files
        config.unlink()
        tracker.unlink()
        for s in _sources:
            s.unlink()
