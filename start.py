import subprocess
import sys
import os
import time

def main():
    print("==================================================")
    print("🚀 Starting Udyam AI Login Assistant")
    print("==================================================")
    print("Starting FastAPI Backend on http://localhost:8000 ...")
    
    # Start Backend
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    time.sleep(2)
    print("Starting React Frontend on http://localhost:5173 ...")
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True
    )
    
    print("\n✅ System running!")
    print("🌐 Frontend URL: http://localhost:5173")
    print("🌐 Backend URL:  http://localhost:8000")
    print("Press Ctrl+C to terminate both servers.\n")
    
    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()

