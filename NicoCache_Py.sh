#!/bin/sh

cd $(dirname $0)

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv shell 3.7.0 || pyenv shell --unset
export PYTHONPATH=dependency:"$PYTHONPATH"
python3.7 NicoCache_Py.py "$@"
