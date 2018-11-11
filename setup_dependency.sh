#!/bin/bash

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv shell 2.7.10 || pyenv shell --unset

mkdir dependency
pip2.7 install -r requirements.txt --target dependency
