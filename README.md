# LexRAG System

**LexRAG** is a high-precision Retrieval-Augmented Generation (RAG) system designed specifically for the US Tax & Legal domain. It allows legal professionals to ask natural-language questions and receive precise, summarized answers backed by verifiable, exact citations (document name + page number).

This repository contains the complete source code, evaluation metrics, and configuration files to deploy the system.

## 📂 Project Deliverables

All required assignment deliverables are included in this repository:

1. **Overall Approach & Architecture**: See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for a detailed technical document explaining the hybrid retrieval pipeline (ChromaDB + BM25), structural chunking strategy, two-pass citation verification, and NetworkX citation graph integration.
2. **Prompts Used**: See [`PROMPTS.md`](./PROMPTS.md) for the exact system prompts and instructions used for the Claude/Gemini generation models.
3. **Golden Set**: See [`eval/golden_set.csv`](./eval/golden_set.csv) for the evaluation dataset containing 100 domain-specific queries and expected answers used to benchmark system accuracy.
4. **Source Code**: The complete modular codebase is located in `src/` (Python backend) and `ui/` (Next.js frontend).
5. **Deployed UI**: The UI is configured for automated deployment via Vercel (see `vercel.json`), and the FastAPI backend is configured for Render (see `render.yaml`).

## 🚀 Deployment Instructions

### Backend (Render)
1. Connect this repository to Render as a **Web Service**.
2. The platform will automatically detect the `render.yaml` file.
3. Ensure you manually set your API key in the Render dashboard Environment Variables (e.g., `ANTHROPIC_API_KEY` or `GOOGLE_API_KEY`).

### Frontend (Vercel)
1. Import this repository into Vercel.
2. Vercel will automatically read the `vercel.json` file.
3. *Note: If Vercel has trouble detecting the framework, go to the project settings and set the **Root Directory** to `ui`.*
4. Set the `NEXT_PUBLIC_API_URL` environment variable to your deployed Render backend URL (e.g., `https://lexrag-backend.onrender.com`).

## 💻 Local Development Setup

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/sakshivedi-1/US_LexRAG_System.git
cd US_LexRAG_System

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend requirements
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the root directory (do **NOT** commit this file). Refer to `.env.example` for the required keys:
```env
ANTHROPIC_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

### 3. Run the Backend
```bash
uvicorn src.generation.api:app --reload --port 8000
```
*The API will be available at `http://localhost:8000`*

### 4. Run the Frontend
In a new terminal window:
```bash
cd ui
npm install
npm run dev
```
*The Next.js UI will be available at `http://localhost:3000`*

## 🔒 Security Note
This repository strictly utilizes `.gitignore` to prevent any sensitive credentials, `.env` files, or API keys from being committed. Always use environment variables for keys.
