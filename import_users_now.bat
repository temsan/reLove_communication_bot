@echo off
echo ============================================================
echo IMPORT USERS FROM RELOVE CHANNELS
echo ============================================================
echo.

echo Step 1: Testing Telethon connection...
python scripts/telegram/test_telethon_connection.py
if errorlevel 1 (
    echo.
    echo ERROR: Telethon connection failed!
    echo Please authorize first.
    pause
    exit /b 1
)

echo.
echo Step 2: Importing users from all reLove channels...
python scripts/profiles/fill_profiles_from_channels.py --all --no-fill

echo.
echo ============================================================
echo IMPORT COMPLETED
echo ============================================================
echo.
echo Check logs/fill_profiles_from_channels.log for details
pause
