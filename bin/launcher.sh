#!/bin/sh
# Spotify Kindle Launcher for Jailbroken Kindle Paperwhite 1
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="/tmp/kindle-spotify.pid"
PORT=5050

case "$1" in
  start)
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
    
    if [ -f "$PID_FILE" ]; then
      kill -9 $(cat "$PID_FILE") 2>/dev/null
      rm -f "$PID_FILE"
    fi
    
    cd "$APP_DIR"
    python3 server.py --no-browser > /tmp/spotify.log 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    eips -c 2>/dev/null
    lipc-set-prop com.lab126.appmgrd start "app://com.lab126.browser?view=http://127.0.0.1:${PORT}/kindle" 2>/dev/null
    ;;
  stop)
    if [ -f "$PID_FILE" ]; then
      kill -9 $(cat "$PID_FILE") 2>/dev/null
      rm -f "$PID_FILE"
    fi
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
    eips 2 2 "Spotify Kindle Stopped (Sleep Restored)" 2>/dev/null
    ;;
esac
