# ################################################################################
# Xboinc Package — CERN (2025)
# ################################################################################
# Only change this file just before a minor version bump (with a separate commit).
# Avoid diverging xboinc versions with out-of-sync executables.
# ################################################################################

cmake_minimum_required(VERSION 3.16)
project(xboinc VERSION 0.5.0 LANGUAGES C CXX)

# === Compiler and Build Options ===
set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# === Paths (to be set!) ===
set(XTRACK_PYTHON_DIR "/path/to/xtrack/" CACHE PATH "XTrack Python package dir")

# === Target developer triplet (overridable) ===
set(VCPKG_TARGET_TRIPLET "x64-linux" CACHE STRING "VCPKG target triplet")

# === Flags and Definitions ===
set(COMMON_COMPILE_FLAGS -Wall -W -Wshadow -Wpointer-arith -Wcast-qual -Wcast-align -Wunused-parameter -Wno-write-strings -fno-common -O2)
set(COMMON_DEFINITIONS XO_CONTEXT_CPU XO_CONTEXT_CPU_SERIAL)
set(SYSTEM_LIBS pthread m)

# === Sources ===
set(XTRACK_SOURCES xtrack.c)
set(XTRACK_HEADERS xtrack_tracker.h xb_input.h xtrack.h)
set(MAIN_SOURCES main.cpp)

# === Object Library ===
add_library(xtrack_obj OBJECT ${XTRACK_SOURCES})
target_compile_options(xtrack_obj PRIVATE ${COMMON_COMPILE_FLAGS})
target_compile_definitions(xtrack_obj PRIVATE ${COMMON_DEFINITIONS})
target_include_directories(xtrack_obj PRIVATE ${XTRACK_PYTHON_DIR})
target_link_libraries(xtrack_obj PRIVATE m)

# === Executable: xboinc_test (no BOINC) ===
add_executable(xboinc_test ${MAIN_SOURCES})
target_compile_options(xboinc_test PRIVATE ${COMMON_COMPILE_FLAGS})
target_compile_definitions(xboinc_test PRIVATE ${COMMON_DEFINITIONS})
target_include_directories(xboinc_test PRIVATE ${XTRACK_PYTHON_DIR})
target_link_directories(xboinc_test PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(xboinc_test PRIVATE xtrack_obj ${SYSTEM_LIBS})

target_link_options(xboinc_test PRIVATE -static)

# === Executable with BOINC integration ===
if(VCPKG_ROOT AND EXISTS "${VCPKG_ROOT}/installed/${VCPKG_TARGET_TRIPLET}/lib")
    find_library(BOINCAPI_LIB boincapi PATHS ${VCPKG_ROOT}/installed/${VCPKG_TARGET_TRIPLET}/lib)
    find_library(BOINC_LIB boinc PATHS ${VCPKG_ROOT}/installed/${VCPKG_TARGET_TRIPLET}/lib)

    if(BOINCAPI_LIB AND BOINC_LIB)
        add_executable(xboinc ${MAIN_SOURCES})
        include_directories(${VCPKG_ROOT}/installed/${VCPKG_TARGET_TRIPLET}/include/boinc)
        link_directories(${VCPKG_ROOT}/installed/${VCPKG_TARGET_TRIPLET}/lib)
        target_compile_options(xboinc PRIVATE ${COMMON_COMPILE_FLAGS})
        target_compile_definitions(xboinc PRIVATE ${COMMON_DEFINITIONS} COMPILE_TO_BOINC)
        target_include_directories(xboinc PRIVATE ${XTRACK_PYTHON_DIR})
        target_link_directories(xboinc PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
        target_link_libraries(xboinc PRIVATE xtrack_obj ${BOINCAPI_LIB} ${BOINC_LIB} ${SYSTEM_LIBS})
        target_link_options(xboinc PRIVATE
            -static
            -static-libstdc++
            -static-libgcc
            -Wl,--exclude-libs,ALL
        )
        set(XBOINC_ENABLED TRUE)
    else()
        message(STATUS "BOINC libraries not found; 'xboinc' will not be built.")
        set(XBOINC_ENABLED FALSE)
    endif()
else()
    message(STATUS "VCPKG_ROOT is unset or invalid; skipping BOINC integration.")
    set(XBOINC_ENABLED FALSE)
endif()

# === Installation ===
if(XBOINC_ENABLED)
    install(TARGETS xboinc xboinc_test RUNTIME DESTINATION bin COMPONENT Runtime)
else()
    install(TARGETS xboinc_test RUNTIME DESTINATION bin COMPONENT Runtime)
endif()

# === Build Info ===
message(STATUS "=== XBoinc Build Configuration ===")
message(STATUS "Version:             ${PROJECT_VERSION}")
message(STATUS "XTrack Python Dir:   ${XTRACK_PYTHON_DIR}")
message(STATUS "C Compiler:          ${CMAKE_C_COMPILER}")
message(STATUS "C++ Compiler:        ${CMAKE_CXX_COMPILER}")
message(STATUS "Build Type:          ${CMAKE_BUILD_TYPE}")
message(STATUS "VCPKG Root:          ${VCPKG_ROOT}")
message(STATUS "VCPKG Target Triplet:${VCPKG_TARGET_TRIPLET}")
message(STATUS "BOINC API Library:   ${BOINCAPI_LIB}")
message(STATUS "BOINC Library:       ${BOINC_LIB}")
message(STATUS "CMake Build Type:    ${CMAKE_BUILD_TYPE}")
message(STATUS "===============================================")

if(XBOINC_ENABLED)
    message(STATUS "Executables:         xboinc_test xboinc")
else()
    message(STATUS "Executables:         xboinc_test")
endif()

message(STATUS "===============================================")
