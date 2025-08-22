# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2024.                 #
########################################### #


import numpy as np

import xtrack as xt
import xpart as xp
import xboinc as xb


user = 'sixtadm'
line = xt.Line.from_json(xb._pkg_root.parent / 'tests' / 'data' / 'lhc_2024_30cm_b1.json')
line.build_tracker()

# Each of these jobs takes ~3h  (~3500 particle*turns / second)
num_jobs = 250
num_part_per_job = 400
num_turns = 100000
checkpoint_every = 1000

all_part = line.build_particles(x_norm=np.random.normal(0, 10, num_part_per_job*num_jobs),
                                y_norm=np.random.normal(0, 10, num_part_per_job*num_jobs),
                                nemitt_x=3.5e-6, nemitt_y=3.5e-6)

# Do the submission
study_name = "example_study"
jobs = xb.JobSubmitter(user=user, study_name=study_name, line=line, dev_server=True)
prev = time.time()
for i in range(num_jobs):
    # select subgroup of particles
    this_part = all_part.filter((all_part.particle_id>=i*num_part_per_job) \
                                & (all_part.particle_id<(i+1)*num_part_per_job))
    # create job
    jobs.add(job_name=f'job{i}', num_turns=num_turns, particles=this_part,
             checkpoint_every=checkpoint_every)
    # output progress
    if i%25 == 24:
        now = time.time() ; print(f"{i+1}/{num_jobs}  ({now-prev:.4}s)"); prev = now
jobs.submit()


# Alternatively, instead of manually looping over each job, you can use the `slice_and_add` method to create n jobs:
study_name = "example_study_2"
jobs = xb.JobSubmitter(user=user, study_name=study_name, line=line, dev_server=True)
jobs.slice_and_add(base_job_name='job', num_turns=num_turns, particles=all_part,
                   checkpoint_every=checkpoint_every)
jobs.submit()
