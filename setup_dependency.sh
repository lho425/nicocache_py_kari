#!/bin/bash

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv shell 2.7.10 || pyenv shell --unset

mkdir dependency
python2.7 -m pip install -r requirements.txt --target dependency
