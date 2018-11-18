#!/bin/bash

git clone https://github.com/pyenv/pyenv.git

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv install 3.7.0
pyenv shell 3.7.0

python -V
which python
