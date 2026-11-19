@echo off
title AgentForce AI Launcher
echo ===================================================
echo           Starting AgentForce AI Platform
echo ===================================================

echo [1/2] Launching FastAPI Backend on Port 8000...
start "AgentForce Backend (Port 8000)" cmd /k "backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000 --reload"

echo [2/2] Launching Next.js Frontend on Port 3000...
start "AgentForce Frontend (Port 3000)" cmd /k "npm --prefix frontend run dev"

echo.
echo ===================================================
echo Both services are now running in separate windows!
echo - Frontend: http://localhost:3000
echo - Backend:  http://localhost:8000
echo - Docs:     http://localhost:8000/docs
echo ===================================================
echo To stop the servers, simply close both opened windows.
pause
