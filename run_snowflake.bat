@echo off
cd /d "%~dp0"
echo Installing packages, please wait...
pip install pandas numpy "snowflake-connector-python[pandas]"
echo.
set /p SNOWFLAKE_ACCOUNT=Type your account identifier and press Enter: 
set /p SNOWFLAKE_USER=Type your Snowflake username and press Enter: 
set /p SNOWFLAKE_PASSWORD=Type your Snowflake password and press Enter: 
echo.
python generate_data.py
python pipeline.py --target snowflake
echo.
echo Finished. Copy any error above if something went wrong.
pause
