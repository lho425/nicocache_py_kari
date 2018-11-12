@echo off
cd /d %~dp0
shift

mkdir dependency
"C:\Python27\python.exe" -m pip install -r requirements.txt --target dependency