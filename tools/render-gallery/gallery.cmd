@echo off
REM One-tap launcher for the render gallery. Save as a Termius snippet.
REM Override the folder with:  set COMFY_OUTPUT=D:\somewhere\output
setlocal
set PORT=8777
python "%~dp0server.py" --port %PORT% %*
endlocal
