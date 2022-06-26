#!/bin/bash

export PATH=$EXTRA_PATH:$PATH
source /opt/rh/llvm-toolset-7/enable

bash $@

