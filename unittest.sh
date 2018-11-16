#!/bin/sh

cd $(dirname "$0")

python2 -m unittest discover -s ./nicocache/ -t ./nicocache
