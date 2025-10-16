@echo off
title Discord bot Starter
echo ==============================
echo   Starting Discord bot...
echo ==============================

:: go to bot folder
cd /d "C:\Users\supra\Desktop\DiscordBot"

echo Running in:
cd
echo ==============================

:loop
"C:\Users\supra\AppData\Local\Programs\Python\Python313\python.exe" "bot.py"
echo.
echo Bot crashed or stopped. Restarting in 5 seconds...
timeout /t 5 >nul
goto loop
