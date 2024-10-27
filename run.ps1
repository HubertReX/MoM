# .venv\Scripts\activate.bat
Set-Location project
# Write-Output Started...
# austin -i 100 --pipe  python.exe main.py
# pass '-h' parameter to see command line help
python.exe main.py $args

Set-Location ..
