#!/bin/bash

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3.12 -m venv .venv
    
    echo "Activating virtual environment..."
    source .venv/bin/activate
    
    echo "Installing requirements..."
    pip install -r requirements.txt
else
    echo "Virtual environment already exists, activating..."
    source .venv/bin/activate
fi

echo "Making script executable..."
chmod +x src/twitta.py

echo "Starting Twitta..."
python src/twitta.py

echo ""
echo "If you want to run Twitta again later, just use:"
echo "source .venv/bin/activate"
echo "python3 twitta.py"