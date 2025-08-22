# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
########################################### #

import xboinc as xb

list_of_succeeded_jobs = []
user='sixtadm'
study_name='example_study'
for jobname, new_particles in xb.JobRetriever(user=user, study_name=study_name, dev_server=True):
    print(jobname)
    print(f"Particles: {new_particles.at_turn}")
