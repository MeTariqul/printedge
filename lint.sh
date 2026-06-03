@echo off
REM Lint script to catch undefined names before deployment
python -m flake8 core/ --select=F821 --ignore=E501,W503
if %ERRORLEVEL% NEQ 0 (
    echo "Lint errors found - please fix them before committing"
    exit 1
)
echo "No undefined name errors found"