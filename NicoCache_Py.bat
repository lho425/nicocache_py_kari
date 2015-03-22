@echo off
cd /d %~dp0
shift 


"C:\Python27\python.exe" NicoCache_Py.py  %*
pause
