#!/bin/bash

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv shell 3.7.0 || pyenv shell --unset

mkdir dependency
python3.7 -m pip install -r requirements.txt --target dependency
