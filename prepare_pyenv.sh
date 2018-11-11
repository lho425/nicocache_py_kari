#!/bin/bash

git clone https://github.com/pyenv/pyenv.git

export PYENV_ROOT="$PWD/pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init -)"
fi

pyenv install 2.7.10
pyenv local 2.7.10
python -V
which python
