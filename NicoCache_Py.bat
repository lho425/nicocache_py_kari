@echo off
cd /d %~dp0
shift 

if "%0"=="-nkf32" (
    SET nkf=nkf32
) else (
    SET nkf=nkf
)



"C:\Python27\python.exe" nicocache.py  %*  2>&1| %nkf% -u -W -s
pause