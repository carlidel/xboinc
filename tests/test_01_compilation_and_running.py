# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
########################################### #

import filecmp
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pytest
import xtrack as xt

import xboinc as xb


# NOTE: to have these tests running, you might want to alter some of these parameters!
class TestConfig:
    """Configuration constants for the test suite."""
    
    # Test data files
    LINE_FILE = xb._pkg_root.parent / "tests" / "data" / "lhc_2024_30cm_b1.json"
    
    # Simulation parameters
    NUM_TURNS = 1000
    NUM_PARTICLES = 100
    CHECKPOINT_INTERVAL = 50
    
    # File names
    INPUT_FILE = "xboinc_input.bin"
    OUTPUT_FILE = "xboinc_state_out.bin"
    CHECKPOINT_FILE = "checkpoint.bin"
    
    # Timeout for interrupted tests (seconds)
    CHECKPOINT_TIMEOUT = 15
    
    # VCPKG configuration
    VCPKG_ROOT = Path("/home/user/vcpkg")
    
    @classmethod
    def vcpkg_available(cls) -> bool:
        """Check if VCPKG and BOINC are properly installed."""
        return (
            cls.VCPKG_ROOT.is_dir()
            and cls.VCPKG_ROOT.exists()
            and (cls.VCPKG_ROOT / "installed" / "x64-linux" / "lib" / "libboinc.a").exists()
        )
    
    @classmethod
    def files_to_clean(cls) -> list[str]:
        """List of files that should be cleaned up after tests."""
        return [
            f"./{cls.OUTPUT_FILE}",
            f"./{cls.CHECKPOINT_FILE}",
            "./boinc_finish_called",
        ]


@pytest.fixture(autouse=True)
def cleanup_files():
    """Automatically clean up test files before and after each test."""
    def safe_remove(*files):
        """Remove files silently if they exist."""
        for file_path in files:
            try:
                os.remove(file_path)
            except FileNotFoundError:
                pass
    
    # Cleanup before test
    safe_remove(*TestConfig.files_to_clean())
    yield
    # Cleanup after test
    safe_remove(*TestConfig.files_to_clean())


@pytest.fixture
def skip_version_check():
    """Temporarily disable xsuite version checking during tests."""
    xb._skip_xsuite_version_check = True
    yield
    xb._skip_xsuite_version_check = False


def create_test_particles(at_element: Optional[str] = None) -> Tuple[xt.Line, xt.Particles]:
    """
    Create a standardized line and particle distribution for testing.
    
    Parameters
    ----------
    at_element : str, optional
        Element name or index where particles should start.
        
    Returns
    -------
    tuple[xt.Line, xt.Particles]
        The tracking line and initial particle distribution.
    """
    line = xt.Line.from_json(TestConfig.LINE_FILE)
    line.build_tracker()
    
    x_norm = np.linspace(-15, 15, TestConfig.NUM_PARTICLES)
    delta = np.linspace(-1.0e-5, 1.0e-5, TestConfig.NUM_PARTICLES)
    
    particles = line.build_particles(
        x_norm=x_norm,
        delta=delta,
        nemitt_x=3.5e-6,
        nemitt_y=3.5e-6,
        at_element=at_element,
    )
    
    return line, particles


def get_executable_path(use_boinc: bool) -> Path:
    """
    Get the path to the compiled executable, compiling if necessary.
    
    Parameters
    ----------
    use_boinc : bool
        Whether to get the BOINC-enabled executable.
        
    Returns
    -------
    Path
        Path to the executable file.
    """
    app_name = "xboinc" if use_boinc else "xboinc_test"
    pattern = f"{app_name}_{xb.app_version}-*"
    
    exec_files = list(Path.cwd().glob(pattern))
    if not exec_files or not exec_files[0].exists():
        # Need to compile
        vcpkg_root = TestConfig.VCPKG_ROOT if use_boinc else None
        test_compilation(vcpkg_root)
        exec_files = list(Path.cwd().glob(pattern))
    
    if not exec_files:
        raise RuntimeError(f"Could not find or create executable matching {pattern}")
    
    return exec_files[0]


def run_xboinc_tracking(executable: Path, timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    """
    Execute the xboinc tracking application.
    
    Parameters
    ----------
    executable : Path
        Path to the executable to run.
    timeout : float, optional
        Timeout in seconds. If None, no timeout is applied.
        
    Returns
    -------
    subprocess.CompletedProcess
        The completed process result.
        
    Raises
    ------
    subprocess.CalledProcessError
        If the tracking execution fails.
    subprocess.TimeoutExpired
        If the execution times out.
    """
    cmd_args = [str(executable), "--verbose", "1"]
    
    try:
        return subprocess.run(
            cmd_args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Tracking failed: {e.stderr.decode()}") from e


def assert_particles_equal(particles1: xt.Particles, particles2: xt.Particles, context: str) -> None:
    """
    Assert that two particle objects are equivalent.
    
    Parameters
    ----------
    particles1, particles2 : xt.Particles
        The particle objects to compare.
    context : str
        Description of the comparison context for error messages.
    """
    attributes = ["particle_id", "state", "at_turn", "x", "y", "zeta", "px", "py", "delta"]
    
    for attr in attributes:
        values1 = getattr(particles1, attr)
        values2 = getattr(particles2, attr)
        assert np.array_equal(values1, values2), f"{context}: {attr} values are not equal"


def test_generate_input(skip_version_check):
    """Test input file generation and round-trip consistency."""
    line, particles = create_test_particles()
    input_file = Path.cwd() / TestConfig.INPUT_FILE
    
    # Create input object
    xb_input = xb.XbInput(
        line=line,
        particles=particles,
        num_turns=TestConfig.NUM_TURNS,
        checkpoint_every=TestConfig.CHECKPOINT_INTERVAL,
    )
    
    # Verify input object integrity
    particles_dict_original = particles.to_dict()
    particles_dict_input = xb_input.particles.to_dict()
    
    assert xt.line._dicts_equal(particles_dict_original, particles_dict_input)
    assert list(line.element_names) == list(xb_input.line.element_names)
    
    line_dict_original = line.to_dict()
    line_dict_input = xb_input.line.to_dict()
    assert xt.line._dicts_equal(line_dict_original["elements"], line_dict_input["elements"])
    
    # Test file I/O
    xb_input.to_binary(input_file)
    assert input_file.exists()
    
    # Test round-trip consistency
    loaded_input = xb.XbInput.from_binary(input_file)
    particles_dict_loaded = loaded_input.particles.to_dict()
    
    assert xt.line._dicts_equal(particles_dict_original, particles_dict_loaded)
    assert list(line.element_names) == list(loaded_input.line.element_names)
    
    line_dict_loaded = loaded_input.line.to_dict()
    assert xt.line._dicts_equal(line_dict_original["elements"], line_dict_loaded["elements"])


def test_source_generation(skip_version_check):
    """Test C++ source code generation."""
    xb.generate_executable_source()
    
    expected_files = [
        "main.cpp",
        "CMakeLists.txt", 
        "xtrack.c",
        "xtrack.h",
        "xb_input.h",
        "xtrack_tracker.h",
        "version.h",
    ]
    
    for filename in expected_files:
        file_path = Path.cwd() / filename
        assert file_path.exists(), f"Generated source file {filename} not found"


@pytest.mark.parametrize(
    "vcpkg_root",
    [
        None,
        pytest.param(
            TestConfig.VCPKG_ROOT,
            marks=pytest.mark.skipif(
                not TestConfig.vcpkg_available(),
                reason="VCPKG + BOINC installation not found"
            ),
        ),
    ],
    ids=["w/o BOINC api", "with BOINC api"],
)
def test_compilation(vcpkg_root, skip_version_check):
    """Test compilation of the xboinc executable."""
    keep_source = vcpkg_root is None
    xb.generate_executable(keep_source=keep_source, vcpkg_root=vcpkg_root)
    
    app_name = "xboinc" if vcpkg_root else "xboinc_test"
    pattern = f"{app_name}_{xb.app_version}-*"
    exec_files = list(Path.cwd().glob(pattern))
    
    assert len(exec_files) == 1, f"Expected exactly one executable matching {pattern}"
    executable = exec_files[0]
    
    assert executable.exists(), f"Executable {executable} does not exist"
    assert os.access(executable, os.X_OK), f"Executable {executable} is not executable"


@pytest.mark.parametrize(
    "use_boinc",
    [
        False,
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                not TestConfig.vcpkg_available(),
                reason="VCPKG + BOINC installation not found"
            ),
        ),
    ],
    ids=["w/o BOINC api", "with BOINC api"],
)
def test_tracking_execution(use_boinc, skip_version_check):
    """Test particle tracking execution and output validation."""
    # Ensure input file exists
    if not (Path.cwd() / TestConfig.INPUT_FILE).exists():
        test_generate_input(skip_version_check)
    
    executable = get_executable_path(use_boinc)
    
    # Execute tracking
    start_time = time.time()
    run_xboinc_tracking(executable)
    execution_time = round(time.time() - start_time, 1)
    
    app_name = "Xboinc" if use_boinc else "Xboinc Test"
    print(f"Tracking ({app_name}) completed in {execution_time}s.")
    
    # Validate output
    output_file = Path.cwd() / TestConfig.OUTPUT_FILE
    assert output_file.exists(), "Output file was not created"
    
    xb_state = xb.XbState.from_binary(output_file)
    particles = xb_state.particles
    
    # Check simulation completion
    surviving_particles = len(particles.state[particles.state > 0])
    print(f"{surviving_particles}/{TestConfig.NUM_PARTICLES} particles survived.")
    
    assert np.allclose(particles.s[particles.state > 0], 0, rtol=1e-6, atol=0), "Unexpected s coordinate"
    assert np.all(particles.at_turn[particles.state > 0] == TestConfig.NUM_TURNS), "Unexpected particle turn count"
    assert xb_state.i_turn == TestConfig.NUM_TURNS, "Unexpected simulation turn count"
    
    # Verify particle evolution (not all values should be identical)
    for coord in ["x", "px", "y", "py"]:
        values = getattr(particles, coord)
        assert not np.allclose(values, values[0], rtol=1e-4, atol=0), f"All {coord} values are identical"
    
    # Test output file round-trip
    suffix = "_boinc" if use_boinc else ""
    output_file_2 = Path.cwd() / f"{TestConfig.OUTPUT_FILE}{suffix}_2"
    xb_state.to_binary(output_file_2)
    assert filecmp.cmp(output_file, output_file_2, shallow=False), "Output file round-trip failed"


@pytest.mark.parametrize(
    "use_boinc",
    [
        False,
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                not TestConfig.vcpkg_available(),
                reason="VCPKG + BOINC installation not found"
            ),
        ),
    ],
    ids=["w/o BOINC api", "with BOINC api"],
)
def test_checkpoint_functionality(use_boinc, skip_version_check):
    """Test checkpoint creation and recovery functionality."""
    # Ensure prerequisites exist
    if not (Path.cwd() / TestConfig.INPUT_FILE).exists():
        test_generate_input(skip_version_check)
    
    # Get reference output for comparison
    suffix = "_boinc" if use_boinc else ""
    reference_output = Path.cwd() / f"{TestConfig.OUTPUT_FILE}{suffix}_2"
    if not reference_output.exists():
        test_tracking_execution(use_boinc, skip_version_check)
    
    executable = get_executable_path(use_boinc)
    
    # Phase 1: Run with timeout to create checkpoint
    print(f"Will interrupt execution after {TestConfig.CHECKPOINT_TIMEOUT}s to test checkpointing.")
    
    start_time = time.time()
    try:
        run_xboinc_tracking(executable, timeout=TestConfig.CHECKPOINT_TIMEOUT)
        raise ValueError("Execution completed before timeout - increase CHECKPOINT_TIMEOUT")
    except subprocess.TimeoutExpired:
        interrupt_time = time.time()
        print(f"Interrupted after {round(interrupt_time - start_time, 1)}s. Checking for checkpoint.")
    
    # Verify checkpoint was created
    checkpoint_file = Path.cwd() / TestConfig.CHECKPOINT_FILE
    assert checkpoint_file.exists(), "Checkpoint file was not created during interrupted execution"
    
    # Phase 2: Resume from checkpoint
    print("Resuming from checkpoint...")
    # Remove output files but keep checkpoint
    for file_path in [f"./{TestConfig.OUTPUT_FILE}", "./boinc_finish_called"]:
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass
    
    resume_start = time.time()
    run_xboinc_tracking(executable)
    total_time = time.time() - start_time
    resume_time = time.time() - resume_start
    
    app_name = "Xboinc" if use_boinc else "Xboinc Test"
    print(f"Resumed tracking ({app_name}) completed in {round(resume_time, 1)}s "
          f"(total: {round(total_time, 1)}s).")
    
    # Compare resumed result with reference
    output_file = Path.cwd() / TestConfig.OUTPUT_FILE
    assert output_file.exists(), "Output file not created after resume"
    assert filecmp.cmp(output_file, reference_output, shallow=False), \
        "Checkpointed result differs from reference"


def test_consistency_with_xtrack(skip_version_check):
    """Test that xboinc results match xtrack reference implementation."""
    # Test different starting positions
    test_positions = [None, "ip2", 3500]
    
    for at_element in test_positions:
        print(f"Testing consistency at element: {at_element}")
        
        line, particles = create_test_particles(at_element=at_element)
        
        # Create input file
        input_file = Path.cwd() / TestConfig.INPUT_FILE
        xb_input = xb.XbInput(
            line=line,
            particles=particles,
            num_turns=TestConfig.NUM_TURNS,
            checkpoint_every=TestConfig.CHECKPOINT_INTERVAL,
        )
        xb_input.to_binary(input_file)
        
        # Run reference tracking with xtrack
        particles_reference = particles.copy()
        line.track(particles_reference, num_turns=TestConfig.NUM_TURNS, time=True)
        
        # Test standalone xboinc
        executable_test = get_executable_path(use_boinc=False)
        run_xboinc_tracking(executable_test)
        
        output_file = Path.cwd() / TestConfig.OUTPUT_FILE
        xb_state = xb.XbState.from_binary(output_file)
        
        assert_particles_equal(
            particles_reference,
            xb_state.particles,
            f"xboinc_test vs xtrack (at_element={at_element})"
        )
        
        # Test BOINC-enabled xboinc if available
        if TestConfig.vcpkg_available():
            executable_boinc = get_executable_path(use_boinc=True)
            run_xboinc_tracking(executable_boinc)
            
            xb_state_boinc = xb.XbState.from_binary(output_file)
            assert_particles_equal(
                particles_reference,
                xb_state_boinc.particles,
                f"xboinc vs xtrack (at_element={at_element})"
            )
    
    # Test different stop elements
    stop_elements = ["ip2", 3500]
    
    for ele_stop in stop_elements:
        print(f"Testing consistency with stop element: {ele_stop}")
        
        line, particles = create_test_particles()
        
        # Create input with stop element
        input_file = Path.cwd() / TestConfig.INPUT_FILE
        xb_input = xb.XbInput(
            line=line,
            particles=particles,
            num_turns=TestConfig.NUM_TURNS,
            checkpoint_every=TestConfig.CHECKPOINT_INTERVAL,
            ele_stop=ele_stop,
        )
        xb_input.to_binary(input_file)
        
        # Run reference tracking
        particles_reference = particles.copy()
        line.track(particles_reference, num_turns=TestConfig.NUM_TURNS, time=True, ele_stop=ele_stop)
        
        # Test both executables
        for use_boinc, exec_name in [(False, "xboinc_test"), (True, "xboinc")]:
            if use_boinc and not TestConfig.vcpkg_available():
                continue
                
            executable = get_executable_path(use_boinc)
            run_xboinc_tracking(executable)
            
            output_file = Path.cwd() / TestConfig.OUTPUT_FILE
            xb_state = xb.XbState.from_binary(output_file)
            
            assert_particles_equal(
                particles_reference,
                xb_state.particles,
                f"{exec_name} vs xtrack (ele_stop={ele_stop})"
            )
