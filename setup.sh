#!/bin/bash

git clone https://github.com/pyenv/pyenv.git

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv install 2.7.10
pyenv shell 2.7.10

python -V
which python

mkdir dependency
pip install -r requirements.txt --target dependency
