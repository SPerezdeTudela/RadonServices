@echo off
set SCRIPT_DIR=%~dp0
cd %SCRIPT_DIR%
py "./dinolib/dino.py" --cwd %SCRIPT_DIR% %*
