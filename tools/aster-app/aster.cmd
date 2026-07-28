@echo off
REM One-tap launcher for the Aster phone app. Save as a Termius snippet.
REM Override the output folder with:  set COMFY_OUTPUT=D:\somewhere\output
REM Anything you pass through gets handed to server.py, e.g.  aster.cmd --probe
setlocal
set PORT=8778
python "%~dp0server.py" --port %PORT% %*
endlocal
