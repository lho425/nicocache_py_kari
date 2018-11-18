#!/bin/sh

cd $(dirname "$0")

python3 -m unittest discover -s ./nicocache/ -t ./nicocache "$@"
