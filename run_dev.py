import subprocess
import sys
import time
import os

def run_servers():
    print("=" * 60)
    print("🚀 Starting TenderSense AI Platform...")
    print("=" * 60)
    print("• Backend API: http://127.0.0.1:8000")
    print("• API Swagger Docs: http://127.0.0.1:8000/docs")
    print("• Frontend Dashboard: http://localhost:3000")
    print("=" * 60)

    # Start FastAPI backend
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    )

    # Start Vite frontend
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True
    )

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping TenderSense AI servers...")
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    run_servers()
