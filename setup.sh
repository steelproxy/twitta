#!/bin/bash

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt

echo "Making script executable..."
chmod +x ./twitta.py

echo "Starting Twitta..."
python3 twitta.py

echo ""
echo "If you want to run Twitta again later, just use:"
echo "source .venv/bin/activate"
echo "python3 twitta.py"