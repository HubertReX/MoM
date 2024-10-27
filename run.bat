@echo off
set PYGAME_HIDE_SUPPORT_PROMPT=1
cd project
@REM rich -u --rule-char "#"
@REM pass '-h' parameter to see command line help
python.exe main.py %*

cd ..