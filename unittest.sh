#!/bin/sh

cd $(dirname "$0")
export PYTHONPATH="$PWD"/dependency
python2 -m unittest discover -s ./nicocache/ -t ./nicocache
