@echo off
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    
    echo Installing requirements...
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    echo Virtual environment already exists, activating...
    call .venv\Scripts\activate
)

echo Starting Twitta...
python src/twitta.py

echo.
echo If you want to run Twitta again later, just use:
echo call .venv\Scripts\activate
echo python src/twitta.py
pause
