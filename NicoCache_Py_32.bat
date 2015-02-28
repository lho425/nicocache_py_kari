@echo off


cd /d %~dp0
shift 

NicoCache_Py.bat -nkf32  %*

