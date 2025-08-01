# Instructions for compiling Xboinc executables

The following instructions assume you are operating on an AlmaLinux 9 system with the necessary development tools installed. If you are using a different Linux distribution, package names and commands may vary slightly.

## 1. Requirements

* Development Tools: Ensure you have the necessary development tools installed, including `gcc`, `g++`, `make`, `cmake`, and `git`.
* `python`: ensure you have a healthy Python environment with the `xboinc` package installed, along with its certified dependencies.
* `vcpkg`: current setup uses the `vcpkg` dependency manager to handle BOINC libraries. To install `vcpkg`, follow these steps:

    ```bash
    git clone https://github.com/microsoft/vcpkg.git
    cd vcpkg
    ./bootstrap-vcpkg.sh
    ./vcpkg integrate install
    ```
    After bootstrapping, you can then install the desired library triplets, for the case of BOINC libraries, you can run:
    ```bash
    # for x64 Linux
    ./vcpkg install boinc:x64-linux
    # for x64 Windows
    ./vcpkg install boinc:x64-mingw-static
    ```
* `mingw-w64`: If you are targeting Windows, you will need to install the `mingw-w64` toolchain. On AlmaLinux, you can do this with the following command:
    ```bash
    sudo dnf install mingw64-binutils mingw64-cpp mingw64-crt mingw64-filesystem mingw64-gcc mingw64-gcc-c++ mingw64-headers mingw64-libgcc mingw64-winpthreads mingw64-winpthreads-static
    ```

## 2. Building the Executable

### 2.1 Standard Linux Build

**Without BOINC integration:**
```bash
mkdir build
cd build
python3 -c "import xboinc as xb; xb.generate_executable()"
```

**With BOINC integration:**
```bash
mkdir build-boinc
cd build-boinc
python3 -c "import xboinc as xb; xb.generate_executable(vcpkg_root='/path/to/vcpkg')"
```

### 2.2 Cross-compilation for Windows (MinGW)

**Without BOINC integration:**
```bash
mkdir build-mingw
cd build-mingw
python3 -c "import xboinc as xb; xb.generate_executable(target_triplet='x64-mingw-static')"
```

**With BOINC integration**
```bash
mkdir build-mingw-boinc
cd build-mingw-boinc
python3 -c "import xboinc as xb; xb.generate_executable(vcpkg_root='/path/to/vcpkg', target_triplet='x64-mingw-static')"
```