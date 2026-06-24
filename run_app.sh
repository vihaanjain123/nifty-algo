#!/bin/bash
# Check if already running
if lsof -i:5000 > /dev/null 2>&1; then
    echo "App already running on port 5000"
    exit 0
fi

source /Users/vihaanjain/personalproject/.venv/bin/activate
cd /Users/vihaanjain/nifty-algo
python /Users/vihaanjain/personalproject/app.py >> /Users/vihaanjain/nifty-algo/app.log 2>&1
