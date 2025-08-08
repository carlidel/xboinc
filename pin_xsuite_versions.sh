#!/bin/bash

# copyright ############################### #
# This file is part of the Xboinc Package.  #
# Copyright (c) CERN, 2025.                 #
# ######################################### #

# This script pins XSuite module versions in the Xboinc package.
# It updates version information in general.py, test_version.py, and pyproject.toml.

# ----- Get list of XSuite modules to pin -----
cd xboinc
modules=$(python -c 'from general import __xsuite__versions__; print(" ".join(__xsuite__versions__.keys()))')

if [[ -z "$modules" ]]; then
    echo "Error: Could not retrieve list of XSuite modules to pin!"
    exit 1
fi
cd ..

# ----- Check and display the versions to be pinned -----
echo "The following modules will be pinned:"
for module in $modules; do
    version=$(python -c "import $module; print($module.__version__)")
    
    if [[ -z "$version" ]]; then
        echo "Error: Could not retrieve version for $module"
        exit 1
    fi
    
    echo "  - ${module}: $version"
done

# ----- Ask for confirmation -----
read -n 1 -p "Press y to continue (or any other key to cancel): " answer
echo

case ${answer:0:1} in
    y|Y)
        echo "Proceeding with version pinning..."
        ;;
    *)
        echo "Operation cancelled."
        exit 0
        ;;
esac

# ----- Pin each module version in configuration files -----
echo "Updating version information in configuration files..."
for module in $modules; do
    version=$(python -c "import $module; print($module.__version__)")
    
    if [[ -z "$version" ]]; then
        echo "Error: Could not retrieve version for $module"
        exit 1
    fi
    
    # Update version in three different files with appropriate patterns
    sed -i "s/\('${module}' *:\).*/\1 '${version}',/"  xboinc/general.py
    sed -i "s/\('${module}' *:\).*/\1 '${version}',/"  tests/test_version.py
    sed -i "s/\(${module} *=\).*/\1 '==${version}'/"   pyproject.toml
    
    echo "  - Pinned ${module} to version ${version}"
done

echo "Version pinning completed successfully."
exit 0
