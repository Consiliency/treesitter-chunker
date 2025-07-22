@echo off
REM Build script for Windows
REM Requires Visual Studio Build Tools or Visual Studio 2019/2022

echo Building treesitter-chunker for Windows...

REM Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python not found in PATH
    exit /b 1
)

REM Check for Visual Studio
if not defined VCINSTALLDIR (
    echo Looking for Visual Studio...
    
    REM Try VS 2022
    if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
        call "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    ) else if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" (
        call "%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    ) else if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
        call "%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    ) else if exist "%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
        call "%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    ) else (
        REM Try VS 2019
        if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
            call "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
        ) else if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvars64.bat" (
            call "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvars64.bat"
        ) else if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
            call "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
        ) else if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
            call "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
        ) else (
            echo Error: Visual Studio not found. Please install Visual Studio Build Tools
            echo Download from: https://visualstudio.microsoft.com/downloads/
            exit /b 1
        )
    )
)

echo Using Visual Studio from: %VCINSTALLDIR%

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip wheel setuptools

REM Install build dependencies
echo Installing build dependencies...
pip install build cibuildwheel

REM Fetch and build grammars
echo Fetching grammars...
python scripts\fetch_grammars.py
if %errorlevel% neq 0 (
    echo Error: Failed to fetch grammars
    exit /b 1
)

echo Building grammars...
python scripts\build_lib.py
if %errorlevel% neq 0 (
    echo Error: Failed to build grammars
    exit /b 1
)

REM Build wheel
echo Building wheel...
python -m build --wheel --outdir dist
if %errorlevel% neq 0 (
    echo Error: Failed to build wheel
    exit /b 1
)

echo.
echo Build complete! Check the dist\ directory for the wheel file.
echo.
echo To install: pip install dist\treesitter_chunker-*.whl
echo.

REM Deactivate virtual environment
call venv\Scripts\deactivate.bat