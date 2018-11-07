#!/bin/bash

mkdir -p mitm

openssl genrsa 2048 > mitm/server.key
openssl req -subj '/C=JP/CN=*.nicovideo.jp' -new -key mitm/server.key > mitm/server.csr
openssl x509 -days 36500 -req -signkey mitm/server.key < mitm/server.csr > mitm/server.crt -extfile mitm/san.ext  # -extfile is needed for google chrome 
