#!/bin/sh

cd $(dirname $0)

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv shell 2.7.10
export PYTHONPATH=dependency:"$PYTHONPATH"
python NicoCache_Py.py "$@"
