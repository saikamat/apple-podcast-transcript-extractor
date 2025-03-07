@echo off
echo Starting Podcast Transcript Extractor...

:: Start monitor in background
start /B python monitor_ttml.py > monitor.log 2>&1
echo Monitor started

:: Start web app
start /B python app.py > webapp.log 2>&1
echo Web app started

echo ================================================
echo Podcast Transcript Extractor running!
echo Web interface available at: http://127.0.0.1:5000
echo Close this window to stop all processes
echo ================================================

:: Keep the window open
pause > null