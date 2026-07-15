"""
Railway-compatible startup script.
Reads PORT from environment variable (injected by Railway) and starts uvicorn.
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting LexRAG backend on port {port}...")
    uvicorn.run(
        "src.generation.api:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        timeout_keep_alive=30,
    )
