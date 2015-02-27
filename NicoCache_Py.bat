@echo off


cd /d %~dp0
shift 
"C:\Python27\python.exe" nicocache.py  %*  2>&1| nkf -u -W -s
pause