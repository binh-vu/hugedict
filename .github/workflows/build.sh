#!/bin/bash

set -e

# Description: builds Python's wheels.
# The script needs yum or apt
#
# Envionment Arguments: (handled by `args.py`)
#   PYTHON_HOME: the path to the Python installation, which will be used to build the wheels for. 
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

# ##############################################
echo "::group::Discovering Python"
TMP=$(python $SCRIPT_DIR/pydiscovery.py --min-version 3.8 --root-dir $PYTHON_HOME)
PYTHON_EXECS=($TMP)
if [ ${#PYTHON_EXECS[@]} -eq 0 ]; then
    echo "No Python found. Did you forget to set any environment variable PYTHON_HOME?"
else
    for PYTHON_EXEC in "${PYTHON_EXECS[@]}"
    do
        echo "Found $PYTHON_EXEC"
    done    
fi
echo "::endgroup::"
echo

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
        # centos
        # https://developers.redhat.com/blog/2018/07/07/yum-install-gcc7-clang#
        yum install -y llvm-toolset-7
        source /opt/rh/llvm-toolset-7/enable
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
for PYTHON_EXEC in "${PYTHON_EXECS[@]}"
do
    echo "::group::Building for Python $PYTHON_EXEC"

    echo "Run: maturin build -r -o dist -i $PYTHON_EXEC --target $target"
    "maturin" build -r -o dist -i "$PYTHON_EXEC" --target $target

    echo "::endgroup::"
    echo
done