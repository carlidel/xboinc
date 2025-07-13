# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #


# ===============================================================================================
# IMPORTANT
# ===============================================================================================
# Only make changes to this file just before a minor version bump (need a separate commit though)
# to avoid having multiple xboinc versions with out-of-sync executables.
# ===============================================================================================

# This should work on Linux.  Modify as needed for other platforms.

# If needed, set the BOINC_DIR to the location of your BOINC installation.
# BOINC_DIR = /home/boincadm/boinc

# If needed, set the directory where the xtrack Python package is installed.
# XTRACK_PYTHON_DIR = /home/boincadm/anaconda3/lib/python3.13/site-packages/xtrack

BOINC_SOURCE_API_DIR = $(BOINC_DIR)/api
BOINC_SOURCE_LIB_DIR = $(BOINC_DIR)/lib
BOINC_SOURCE_ZIP_DIR = $(BOINC_DIR)/zip
FREETYPE_DIR = /usr/include/freetype2

BOINC_API_DIR = $(BOINC_SOURCE_API_DIR)
BOINC_LIB_DIR = $(BOINC_SOURCE_LIB_DIR)
BOINC_ZIP_DIR = $(BOINC_SOURCE_ZIP_DIR)

MAKEFILE_STDLIB  = libstdc++.a
MAKEFILE_LDFLAGS = -lpthread $(MAKEFILE_STDLIB) -static

CXXFLAGS += \
    -Wall -W -Wshadow -Wpointer-arith -Wcast-qual -Wcast-align -Wunused-parameter -Wno-write-strings -fno-common \
    -O2 \
	-I$(XTRACK_PYTHON_DIR) \
    -I$(BOINC_DIR) \
    -I$(BOINC_SOURCE_API_DIR) \
    -I$(BOINC_SOURCE_LIB_DIR) \
    -I$(BOINC_SOURCE_ZIP_DIR) \
    -I$(FREETYPE_DIR) \
    -L$(BOINC_API_DIR) \
    -L$(BOINC_LIB_DIR) \
    -L/usr/X11R6/lib \
    -L/usr/lib \
    -L. \
	-DXO_CONTEXT_CPU \
	-DXO_CONTEXT_CPU_SERIAL
# These last two flags are now needed for the xtrack Python package
# to compile the xboinc executable correctly
# For GPU context, different flags are needed, but we are not using them here for now.
# For CPU context, single core, we can use -DXO_CONTEXT_CPU_SERIAL instead of -DXO_CONTEXT_CPU_OPENMP.

# to get the graphics app to compile you may need to install some packages
# e.g. ftgl-devel.x86_64
#
# You may have to change the paths for your system.

LIBGLUT = -lglut
LIBGLU = -lGLU
LIBGL= -lGL
LIBUI = -lX11 -lXmu
LIBFTGL = -lftgl
LIBJPEG = -ljpeg

ifdef BUILD_WITH_VCPKG
  BUILD_DIR     = $(BOINC_DIR)/3rdParty/linux
  VCPKG_DIR     ?= $(BUILD_DIR)/vcpkg/installed/x64-linux

  CXXFLAGS += \
    -I$(VCPKG_DIR)/include \
    -L$(VCPKG_DIR)/lib

  LIBUI = -lX11 -lXmu -lXrandr -lXxf86vm -lXi
  LIBFTGL = -lftgl -lfreetype -lpng -lbz2 -lbrotlidec-static -lbrotlienc-static -lbrotlicommon-static -lz
endif

ifdef BUILD_WITH_MINGW
  LIBGLUT = -lfreeglut_static
  LIBGLU = -lglu32
  LIBGL= -lopengl32
  LIBUI = -lgdi32 -lwinmm
  LIBFTGL = -lftgl -lfreetype -lpng -lbz2 -lbrotlidec-static -lbrotlienc-static -lbrotlicommon-static -lz
endif

PROGS = xboinc xboinc_test
# make this optional so compile doesn't break on systems without OpenGL

$(info All PROGS=$(PROGS))

all: $(PROGS)

$(MAKEFILE_STDLIB):
	ln -s `$(CXX) $(CXXFLAGS) -print-file-name=$(MAKEFILE_STDLIB)`

# ttfont.cpp:
# 	ln -s ../../api/ttfont.cpp .

clean: distclean

distclean:
	/bin/rm -f $(PROGS) $(addsuffix .exe, $(PROGS)) *.o $(MAKEFILE_STDLIB)

install: xboinc

# specify library paths explicitly (rather than -l)
# because otherwise, you might get a version in /usr/lib etc.

xtrack.o: xtrack_tracker.h xb_input.h xtrack.c
	$(CC) $(CXXFLAGS) -lm -std=c99 -c xtrack.c

xboinc_test: xtrack.o xtrack.h main.c $(MAKEFILE_STDLIB)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -o xboinc_test xtrack.o main.c -lm $(MAKEFILE_LDFLAGS)

xboinc: xtrack.o main.c $(MAKEFILE_STDLIB) $(BOINC_API_DIR)/libboinc_api.a $(BOINC_LIB_DIR)/libboinc.a
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(LDFLAGS) -DCOMPILE_TO_BOINC -o xboinc xtrack.o main.c \
	-lm -lboinc_api -lboinc $(MAKEFILE_LDFLAGS) \
	$(STDCPPTC)
