@echo off
echo Creating virtual environment...
python -m venv .venv

echo Activating virtual environment...
call .venv\Scripts\activate

echo Installing requirements...
pip install -r requirements.txt

echo Starting Twitta...
python twitta.py

echo.
echo If you want to run Twitta again later, just use:
echo call .venv\Scripts\activate
echo python twitta.py
pause
