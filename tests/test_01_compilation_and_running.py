# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
########################################### #

import subprocess
import numpy as np
from pathlib import Path
import os
import time
import filecmp
import pytest

import xtrack as xt
import xboinc as xb


line_file = xb._pkg_root.parent / "tests" / "data" / "lhc_2024_30cm_b1.json"
num_turns = 1000
num_part = 100

input_filename = "xboinc_input.bin"
output_filename = "xboinc_state_out.bin"
checkpoint_filename = "checkpoint.bin"

boinc_path = xb._pkg_root.parents[1] / "boinc"
boinc_api = boinc_path / "api" / "libboinc_api.a"
boinc_lib = boinc_path / "lib" / "libboinc.a"
boinc_missing = (
    not boinc_path.is_dir()
    or not boinc_path.exists()
    or not boinc_api.exists()
    or not boinc_lib.exists()
)


def _make_input(at_element=None):
    line = xt.Line.from_json(line_file)
    line.build_tracker()
    x_norm = np.linspace(-15, 15, num_part)
    delta = np.linspace(-1.0e-5, 1.0e-5, num_part)
    part = line.build_particles(
        x_norm=x_norm,
        delta=delta,
        nemitt_x=3.5e-6,
        nemitt_y=3.5e-6,
        at_element=at_element,
    )
    return line, part


def test_generate_input():
    xb._skip_xsuite_version_check = True
    line, part = _make_input()
    input_file = Path.cwd() / input_filename
    input = xb.XbInput(
        line=line, particles=part, num_turns=num_turns, checkpoint_every=50
    )

    # Verify that the line and particles are correct
    part_dict_1 = part.to_dict()
    part_dict_2 = input.particles.to_dict()
    assert xt.line._dicts_equal(part_dict_1, part_dict_2)
    assert list(line.element_names) == list(input.line.element_names)
    line_dict_1 = line.to_dict()
    line_dict_2 = input.line.to_dict()
    assert xt.line._dicts_equal(line_dict_1["elements"], line_dict_2["elements"])

    # Dump to file
    input.to_binary(input_file)
    assert input_file.exists()

    # Test round-trip by loading the file back in
    new_input = xb.XbInput.from_binary(input_file)
    part_dict_3 = new_input.particles.to_dict()
    assert xt.line._dicts_equal(part_dict_1, part_dict_3)
    assert list(line.element_names) == list(new_input.line.element_names)
    line_dict_3 = new_input.line.to_dict()
    assert xt.line._dicts_equal(line_dict_1["elements"], line_dict_3["elements"])
    xb._skip_xsuite_version_check = False


def _get_input():
    input_file = Path.cwd() / input_filename
    if not input_file.exists():
        test_generate_input()


def test_source():
    xb._skip_xsuite_version_check = True
    xb.generate_executable_source()
    assert Path(Path.cwd() / "main.c").exists()
    assert Path(Path.cwd() / "Makefile").exists()
    assert Path(Path.cwd() / "xtrack.c").exists()
    assert Path(Path.cwd() / "xtrack.h").exists()
    assert Path(Path.cwd() / "xb_input.h").exists()
    assert Path(Path.cwd() / "xtrack_tracker.h").exists()
    assert Path(Path.cwd() / "version.h").exists()
    xb._skip_xsuite_version_check = False


@pytest.mark.parametrize(
    "boinc",
    [
        None,
        pytest.param(
            boinc_path,
            marks=pytest.mark.skipif(
                boinc_missing, reason="BOINC installation not found"
            ),
        ),
    ],
    ids=["w/o BOINC api", "with BOINC api"],
)
def test_compilation(boinc):
    xb._skip_xsuite_version_check = True
    keep_source = True if boinc is None else False
    xb.generate_executable(keep_source=keep_source, boinc_path=boinc)
    app = "xboinc_test" if boinc is None else "xboinc"
    exec_file = list(Path.cwd().glob(f"{app}_{xb.app_version}-*"))
    assert len(exec_file) == 1
    assert exec_file[0].exists()
    assert os.access(exec_file[0], os.X_OK)
    xb._skip_xsuite_version_check = False


def _get_exec(boinc):
    app = "xboinc_test" if boinc is None else "xboinc"
    exec_file = list(Path.cwd().glob(f"{app}_{xb.app_version}-*"))
    if len(exec_file) == 0 or not exec_file[0].exists():
        test_compilation(boinc)
    exec_file = list(Path.cwd().glob(f"{app}_{xb.app_version}-*"))
    return exec_file[0]


@pytest.mark.parametrize(
    "boinc",
    [
        None,
        pytest.param(
            boinc_path,
            marks=pytest.mark.skipif(
                boinc_missing, reason="BOINC installation not found"
            ),
        ),
    ],
    ids=["w/o BOINC api", "with BOINC api"],
)
def test_track(boinc):
    xb._skip_xsuite_version_check = True
    exec_file = _get_exec(boinc)
    _get_input()

    # run xboinc tracker
    t1 = time.time()
    try:
        cmd = subprocess.run(
            [exec_file, "--verbose", "1"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Tracking failed.") from e
    calculation_time = round(time.time() - t1, 1)
    app = "Xboinc Test" if boinc is None else "Xboinc"
    print(f"Tracking ({app}) done in {calculation_time}s.")

    # Read output
    output_file = Path.cwd() / output_filename
    assert output_file.exists()
    xb_state = xb.XbState.from_binary(output_file)

    # Look at particles state
    part_xboinc = xb_state.particles
    print(f"{len(part_xboinc.state[part_xboinc.state > 0])}/{num_part} survived.")
    assert np.allclose(
        part_xboinc.s[part_xboinc.state > 0], 0, rtol=1e-6, atol=0
    ), "Unexpected s"
    assert np.all(
        part_xboinc.at_turn[part_xboinc.state > 0] == num_turns
    ), "Unexpected survivals (particles)"
    assert xb_state.i_turn == num_turns, "Unexpected survival (xb_state)"

    # Check that the tracking made sense, i.e. that not all values are the same
    assert not np.allclose(part_xboinc.x, part_xboinc.x[0], rtol=1e-4, atol=0)
    assert not np.allclose(part_xboinc.px, part_xboinc.px[0], rtol=1e-4, atol=0)
    assert not np.allclose(part_xboinc.y, part_xboinc.y[0], rtol=1e-4, atol=0)
    assert not np.allclose(part_xboinc.py, part_xboinc.py[0], rtol=1e-4, atol=0)

    # Test round-trip by dumping the file again
    output_file_2 = (
        Path.cwd() / f"{output_filename}{'' if boinc is None else '_boinc'}_2"
    )
    xb_state.to_binary(output_file_2)
    filecmp.cmp(output_file, output_file_2, shallow=False)
    xb._skip_xsuite_version_check = False
    if (Path.cwd() / checkpoint_filename).exists():
        (Path.cwd() / checkpoint_filename).unlink()


def _get_output(boinc):
    output_file_2 = (
        Path.cwd() / f"{output_filename}{'' if boinc is None else '_boinc'}_2"
    )
    if not output_file_2.exists():
        test_track(boinc)
    return output_file_2


@pytest.mark.parametrize(
    "boinc",
    [
        None,
        pytest.param(
            boinc_path,
            marks=pytest.mark.skipif(
                boinc_missing, reason="BOINC installation not found"
            ),
        ),
    ],
    ids=["w/o BOINC api", "with BOINC api"],
)
def test_checkpoint(boinc):
    xb._skip_xsuite_version_check = True
    exec_file = _get_exec(boinc)
    _get_input()
    output_file_2 = _get_output(boinc)

    # run xboinc tracker and interrupt halfway
    interrupted = False
    # timeout = 0.6*request.config.cache.get('calculation_time', 15)
    timeout = 15
    print(f"Will interrupt after {timeout}s.")
    t1 = time.time()
    try:
        cmd = subprocess.run([exec_file, "--verbose", "1"], timeout=timeout, check=True)
    except subprocess.TimeoutExpired:
        t2 = time.time()
        interrupted = True
        checkpoint_file = Path.cwd() / checkpoint_filename
        assert checkpoint_file.exists()
        print(
            f"Interrupted calculation after {round(t2 - t1, 1)}s. Now trying to continue."
        )
    if not interrupted:
        raise ValueError("Timeout was too short. Adapt the test 'test_checkpoint'.")

    # Now continue tracking (without timeout)
    try:
        cmd = subprocess.run([exec_file, "--verbose", "1"], check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Tracking failed.") from e
    
    t3 = time.time()
    app = "Xboinc Test" if boinc is None else "Xboinc"
    print(
        f"Continued tracking ({app}) done in {round(t3 - t2, 1)}s (total tracking time {round(t3 - t1, 1)}s)."
    )

    # Compare file to previous result
    output_file = Path.cwd() / output_filename
    assert output_file.exists()
    assert filecmp.cmp(output_file, output_file_2, shallow=False)
    xb._skip_xsuite_version_check = False
    if (Path.cwd() / checkpoint_filename).exists():
        (Path.cwd() / checkpoint_filename).unlink()


def assert_particles_equal(part1, part2, label):
    assert np.array_equal(
        part1.particle_id, part2.particle_id
    ), f"{label}: ids are not equal"
    assert np.array_equal(part1.state, part2.state), f"{label}: states are not equal"
    assert np.array_equal(
        part1.at_turn, part2.at_turn
    ), f"{label}: survivals are not equal"
    assert np.array_equal(part1.x, part2.x), f"{label}: x are not equal"
    assert np.array_equal(part1.y, part2.y), f"{label}: y are not equal"
    assert np.array_equal(part1.zeta, part2.zeta), f"{label}: zeta are not equal"
    assert np.array_equal(part1.px, part2.px), f"{label}: px are not equal"
    assert np.array_equal(part1.py, part2.py), f"{label}: py are not equal"
    assert np.array_equal(part1.delta, part2.delta), f"{label}: delta are not equal"


# Remove files if they exist
def safe_remove(*files):
    for f in files:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass

files_to_remove = [
    "./xboinc_state_out.bin",
    "./checkpoint.bin",
    "./boinc_finish_called",
]

def test_vs_xtrack():
    xb._skip_xsuite_version_check = True

    exec_test = _get_exec(boinc=None)
    if not boinc_missing:
        exec_boinc = _get_exec(boinc_path)
    output_file = Path.cwd() / output_filename

    for at_element in [None, "ip2", 3500]:
        line, part = _make_input(at_element=at_element)
        input_file = Path.cwd() / input_filename
        input = xb.XbInput(
            line=line, particles=part, num_turns=num_turns, checkpoint_every=50
        )
        input.to_binary(input_file)
        line.track(part, num_turns=num_turns, time=True)

        try:
            cmd = subprocess.run(
                [exec_test, "--verbose", "1"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Tracking failed.") from e
        xb_state = xb.XbState.from_binary(output_file)
        part_xboinc_test = xb_state.particles
        assert_particles_equal(
            part,
            part_xboinc_test,
            f"xboinc_test failed to match xtrack. at_element={at_element}",
        )
        safe_remove(*files_to_remove)

        if not boinc_missing:
            try:
                cmd = subprocess.run(
                    [exec_boinc, "--verbose", "1"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError("Tracking with BOINC API failed.") from e
            xb_state = xb.XbState.from_binary(output_file)
            part_xboinc = xb_state.particles
            assert_particles_equal(
                part,
                part_xboinc,
                f"xboinc failed to match xtrack. at_element={at_element}",
            )
            safe_remove(*files_to_remove)

    for ele_stop in ["ip2", 3500]:
        line, part = _make_input()
        input_file = Path.cwd() / input_filename
        input = xb.XbInput(
            line=line,
            particles=part,
            num_turns=num_turns,
            checkpoint_every=50,
            ele_stop=ele_stop,
        )
        input.to_binary(input_file)
        line.track(part, num_turns=num_turns, time=True, ele_stop=ele_stop)

        try:
            cmd = subprocess.run(
                [exec_test, "--verbose", "1"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Tracking failed.") from e
        xb_state = xb.XbState.from_binary(output_file)
        part_xboinc_test = xb_state.particles

        assert_particles_equal(
            part,
            part_xboinc_test,
            f"xboinc_test failed to match xtrack. ele_stop={ele_stop}",
        )
        safe_remove(*files_to_remove)

        if not boinc_missing:
            try:
                cmd = subprocess.run(
                    [exec_boinc, "--verbose", "1"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError("Tracking with BOINC API failed.") from e
            xb_state = xb.XbState.from_binary(output_file)
            part_xboinc = xb_state.particles

            assert_particles_equal(
                part,
                part_xboinc,
                f"xboinc failed to match xtrack. ele_stop={ele_stop}",
            )
            safe_remove(*files_to_remove)

    xb._skip_xsuite_version_check = False
