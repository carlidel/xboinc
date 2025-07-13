// copyright ############################### #
// This file is part of the Xboinc Package.  #
// Copyright (c) CERN, 2025.                 #
// ######################################### #


// This file should be compiled separately (in C) in order
// to provide the necessary xsuite functions to main.c

#ifndef NULL
#define NULL 0
#endif
#ifndef M_PI
#define M_PI 3.14159265358979
#endif

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>

// #include "xtrack.h"
#include "xtrack_tracker.h"
#include "xb_input.h"

// gcc -O3 -lm -U__STRICT_ANSI__ -std=c99 -c -o xtrack.o xtrack.c
    