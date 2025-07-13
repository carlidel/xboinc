# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
########################################### #

import tarfile
import numpy as np
import pandas as pd
import subprocess
from pathlib import Path
import time
import shutil
import filecmp
import pytest

import xtrack as xt
import xpart as xp
import xboinc as xb
from xboinc.server import server_account
from xboinc.server.paths import _test_afs


input_dir  = _test_afs / 'input_dev'
output_dir = _test_afs / 'output_dev'
input_filename      = 'xboinc_input.bin'
output_filename     = 'xboinc_state_out.bin'
checkpoint_filename = 'checkpoint.bin'

study_name = "_test_study"

num_turns = 100
num_particles = 5000
checkpoint_every = 25
particles_per_sub = 500
num_jobs = int(num_particles/particles_per_sub)


def test_submission():
    xb._skip_xsuite_version_check = True
    xb.register(server_account, _test_afs)
    num_turns = 100
    num_particles = 5000
    checkpoint_every = 25
    line = xt.Line(elements=[
        xt.Drift(length=1.0), xt.Multipole(knl=[1e-4]), xt.Drift(length=1.0)])
    # line = xt.Line.from_json(xb._pkg_root.parent / 'tests' / 'data' / 'lhc_2024_30cm_b1.json')

    # Clean potential leftover from failed test
    for file in input_dir.glob(f"{server_account}__*"):
        if file.is_dir():
            shutil.rmtree(file)
        else:
            file.unlink()
    for file in output_dir.glob(f"{server_account}__*"):
        if file.is_dir():
            shutil.rmtree(file)
        else:
            file.unlink()

    jobs = xb.JobManager(user=server_account, study_name=f"{study_name}_1", line=line, dev_server=True)
    for i in range(num_jobs):
        particles = xp.Particles(x=np.random.normal(0, 0.01, particles_per_sub),
                                 y=np.random.normal(0, 0.003, particles_per_sub))
        jobs.add(job_name=f'{study_name}_1_job{i}', num_turns=num_turns, particles=particles,
                checkpoint_every=checkpoint_every)
    jobs.submit()
    with pytest.raises(ValueError):
        jobs.add(job_name='test', num_turns=num_turns, line=line, particles=xp.Particles(),
                checkpoint_every=checkpoint_every)

    time.sleep(5)
    jobs = xb.JobManager(user=server_account, study_name=f"{study_name}_2", line=line, dev_server=True)
    for i in range(num_jobs):
        particles = xp.Particles(x=np.random.normal(0, 4.7, particles_per_sub),
                                 y=np.random.normal(0, 0.39, particles_per_sub))
        jobs.add(job_name=f'{study_name}_2_job{i}', num_turns=num_turns, particles=particles,
                checkpoint_every=checkpoint_every)
    jobs.submit()

    time.sleep(5)
    with pytest.raises(NotImplementedError):
        jobs = xb.JobManager(user=server_account, study_name=f"{study_name}_3", line=line)

    now = pd.Timestamp.now().timestamp()
    tarfiles = list(input_dir.glob(f"{server_account}__{study_name}_?__*"))
    assert len(tarfiles) == 2
    # Look for the tar that is just generated
    for tar in tarfiles:
        ts = tar.name.split('__')[-1].split('.')[0].replace('_','T').replace('-', ':').replace(':', '-', 2)
        if abs(now - pd.Timestamp(ts).timestamp()) < 60:
            break
    assert tar.exists() and tar.stat().st_size!=0
    tar_contents = tarfile.open(tar)
    members = tar_contents.getmembers()
    assert len(members) == 2*num_jobs
    assert np.all([member.size > 8 for member in members])
    member_names = [member.name for member in members]
    assert len(member_names) == 2*num_jobs
    assert np.all([member[:len(server_account)+2] == f'{server_account}__' for member in member_names])
    assert len([member for member in member_names if member[-5:]=='.json']) == num_jobs
    assert len([member for member in member_names if member[-4:]=='.bin']) == num_jobs
    xb._skip_xsuite_version_check = False
    xb.deregister(server_account)


def test_running():
    exec_file = list(Path.cwd().glob(f'xboinc_test_{xb.app_version}-*'))
    if len(exec_file) == 0 or not exec_file[0].exists():
        raise ValueError("No executable found! Check order of tests.")
    exec_file = exec_file[0]
    exec_file_boinc = list(Path.cwd().glob(f'xboinc_{xb.app_version}-*'))
    if len(exec_file_boinc) == 0 or not exec_file_boinc[0].exists():
        raise ValueError("No executable with boinc API found! Check order of tests.")
    exec_file_boinc = exec_file_boinc[0]

    for tar in input_dir.glob(f"{server_account}__*.tar.gz"):
        xb.server.untar(tar)

    json_files = list(input_dir.glob(f"{server_account}__*/*.json"))
    if len(json_files) == 0:
        raise FileNotFoundError("No json files in server directory!")

    # Run all jobs
    for json_file in json_files:
        bin_file = json_file.with_suffix('.bin')
        input_name = bin_file
        xb.server.fs_mv(bin_file, Path.cwd() / input_filename)
        out_file = Path.cwd() / output_filename
        # Run with BOINC API
        cmd = subprocess.run([exec_file_boinc, '--verbose', '1'])
        if cmd.returncode != 0:
            raise RuntimeError(f"Tracking of file {input_name} with BOINC API failed.")
        xb.server.fs_mv(out_file, Path.cwd() / f"{output_filename}_boinc")
        if (Path.cwd() / checkpoint_filename).exists():
            (Path.cwd() / checkpoint_filename).unlink()
        # Run without BOINC API
        cmd = subprocess.run([exec_file, '--verbose', '1'])
        if cmd.returncode != 0:
            raise RuntimeError(f"Tracking of file {input_name} failed.")
        # Compare
        if not filecmp.cmp(output_filename, f"{output_filename}_boinc", shallow=False):
            raise RunTimeError("Tracking with and without BOINC API produced different results!")
        # Move output
        xb.server.fs_mv(out_file, input_name)

    # Collect output in tars, putting more jobs in each tar
    ii = 1
    while len(json_files) > 0:
        tar = output_dir / f"{server_account}__{xb.server.timestamp(ms=True)}.tar.gz"
        with tarfile.open(tar, "w:gz") as tar:
            for json_file in json_files[:ii]:
                tar.add(json_file, arcname=json_file.name)
                binfile = json_file.with_suffix('.bin')
                tar.add(binfile, arcname=binfile.name)
                json_file.unlink()
                binfile.unlink()
            ii += 1
        json_files = list(input_dir.glob(f"{server_account}__*/*.json"))
        time.sleep(0.5)

    # Clean folders
    for folder in input_dir.glob('*/'):
        folder.rmdir()


def test_retrieval():
    xb._skip_xsuite_version_check = True
    xb.register(server_account, _test_afs)
    for this_study_name in [f"{study_name}_1", f"{study_name}_2"]:
        this_num_jobs = 0
        x_mean_prev = 0
        x_std_prev = 0
        y_mean_prev = 0
        y_std_prev = 0
        for particles, job in xb.RetrieveJobs(user=server_account, study_name=this_study_name, dev_server=True):
            assert job['user'] == server_account
            assert job['study_name'] == this_study_name
            this_num_jobs += 1
            x_mean = np.mean(particles.x)
            x_std = np.std(particles.x)
            y_mean = np.mean(particles.y)
            y_std = np.std(particles.y)
            assert not (np.isclose(x_mean, x_mean_prev)
                        and np.isclose(x_std, x_std_prev)
                        and np.isclose(y_mean, y_mean_prev)
                        and np.isclose(y_std, y_std_prev))
            x_mean_prev = x_mean
            x_std_prev = x_std
            y_mean_prev = y_mean
            y_std_prev = y_std
            print(f"Job {job['job_name']} : x = {x_mean:.4} +- {x_std:.4}  "\
                + f"y = {y_mean:.4} +- {y_std:.4}")
            
        assert this_num_jobs == num_jobs
    xb._skip_xsuite_version_check = False
    xb.deregister(server_account)

