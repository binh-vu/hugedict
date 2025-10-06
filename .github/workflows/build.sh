#!/bin/bash

set -e

# Description: builds Python's wheels.
# The script needs yum or apt
#
# Envionment Arguments: (handled by `args.py`)
#   PYTHON_MIN_VERSION: minimum Python version to build for. This is used to find the Python interpreters.
#   PYTHON_ROOT_DIR: path to the Python installation. This is used to find the Python interpreters.
# Arguments:
#   -t <target>: target platform. See https://doc.rust-lang.org/nightly/rustc/platform-support.html

export PATH=$EXTRA_PATH:$PATH

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

while getopts t: flag
do
    case "${flag}" in
        t) target=${OPTARG};;
    esac
done

if [ -z "$target" ]
then
    echo "target is not set (-t <target>). See more: https://doc.rust-lang.org/nightly/rustc/platform-support.html"
    exit 1
fi

echo "::group::Setup build tools"
# ##############################################
# to build rocksdb, we need CLang and LLVM
echo "Install CLang and LLVM"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! command -v yum &> /dev/null
    then
        # debian
        apt update
        apt install -y clang-11
    else
        # almalinux
        yum install -y llvm-toolset
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Skip on MacOS. Assuming you have CLang and LLVM installed."    
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

# ##############################################
echo "Install Rust"
if ! command -v cargo &> /dev/null
then
    # install rust and cargo
    curl --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable
    source $HOME/.cargo/env
else
    echo "Rust is already installed."
    rustup show
fi

if [ ! -d $(rustc --print target-libdir --target "$target" ) ]
then
    rustup target add $target;
fi

echo "::endgroup::"
echo

# ##############################################
echo "Install Maturin"
if ! command -v maturin &> /dev/null
then
    pip install maturin
else
    echo "Maturin is already installed."
fi

# ##############################################
echo "::group::Discovering Python"
pip install wherepy  # to find local Python interpreters
IFS=':' read -a PYTHON_INTERPRETERS < <(python -m wherepy --minimum-version "$PYTHON_MIN_VERSION" --return-execpath --search-dir "$PYTHON_ROOT_DIR")
if [ ${#PYTHON_INTERPRETERS[@]} -eq 0 ]; then
    echo "No Python found. Did you forget to set the environment variable PYTHON_ROOT_DIR?"
else
    for PYTHON_INTERPRETER in "${PYTHON_INTERPRETERS[@]}"
    do
        echo "Found $PYTHON_INTERPRETER"
    done
fi
echo "::endgroup::"
echo

# ##############################################
PYTHON_INTERPRETERS_JOINED=$(IFS=' ' ; echo "${PYTHON_INTERPRETERS[*]/#/-i }")

echo "::group::Building for Python ${PYTHON_INTERPRETERS[@]}"

echo "Run: maturin build -r -o dist $PYTHON_INTERPRETERS_JOINED --target $target"
maturin build -r -o dist $PYTHON_INTERPRETERS_JOINED --target $target

echo "::endgroup::"
echo
