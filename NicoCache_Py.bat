@echo off
cd /d %~dp0
shift 


"C:\Python27\python.exe" nicocache.py  %*
pause
