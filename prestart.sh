#!/bin/bash
# Overwrite espn_api's requests module with our patched version
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
cp -f vendor/espn_api/requests/espn_requests.py $SITE_PACKAGES/espn_api/requests/espn_requests.py
echo "Patched espn_api"
uvicorn main:app --host 0.0.0.0 --port $PORT
