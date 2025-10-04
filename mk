#!/bin/bash
##
# Author: Karran Dhillon
# 
# Bash script to automate the build and run process 
#
# Date: October 2025
#
# Copyright 2025 SnowAngel-UAV
##

set -e

BUILD_DIR="board/build"
EXECUTABLE="snow_angel_uav_app"

show_help() {
    echo "Usage: ./mk [OPTION]"
    echo ""
    echo "Automate build and run for SnowAngel-UAV."
    echo ""
    echo "Options:"
    echo "  --build-only    Only build the project, do not run the executable."
    echo "  --clean         Delete the build directory before building."
    echo "  -h, --help      Show this help message and exit."
}

BUILD_ONLY=0
CLEAN=0

for arg in "$@"; do
    case $arg in
        --build-only)
            BUILD_ONLY=1
            ;;
        --clean)
            CLEAN=1
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
    esac
done

if [[ $CLEAN -eq 1 ]]; then
    echo "Cleaning build directory..."
    rm -rf "$BUILD_DIR"
    exit 0
fi

# Create build directory if it doesn't exist
mkdir -p "$BUILD_DIR"

# Navigate to build directory
cd "$BUILD_DIR"

# Run cmake
cmake ..

# Build the project
make

if [[ $BUILD_ONLY -eq 1 ]]; then
    echo "Build completed. Skipping execution (--build-only flag set)."
    exit 0
fi

# Run the executable
if [ -f "$EXECUTABLE" ]; then
    echo "Running $EXECUTABLE..."
    ./"$EXECUTABLE"
else
    echo "Executable $EXECUTABLE not found!"
    exit 1
fi