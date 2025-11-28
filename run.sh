#!/bin/bash
# DAD - Database Administration Dashboard
# Startup script

echo "Starting DAD - Database Administration Dashboard..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Create necessary directories
mkdir -p environments
mkdir -p static
mkdir -p templates

# Start the Flask application
echo ""
echo "Starting Flask server on http://0.0.0.0:5000"
echo "Press Ctrl+C to stop"
echo ""
python3 backend/app.py

