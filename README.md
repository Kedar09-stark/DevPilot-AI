# DevPilot AI

DevPilot AI is an AI-powered repository assistant that helps developers understand and explore GitHub codebases using natural-language questions.

## Features

- **GitHub Repository Ingestion:** Fetch and process source files from public GitHub repositories.
- **Code Chunking:** Split source files into smaller chunks for retrieval.
- **Semantic Search:** Find relevant code using vector embeddings.
- **Reranking:** Reorder retrieved code snippets using a cross-encoder model.
- **Repository Q&A:** Ask questions about indexed code and receive answers grounded in retrieved context.
- **Source References:** View the files and line ranges associated with retrieved code.
- **Repository Switching:** Work with different indexed repositories.
- **Local LLM:** Generate responses using Ollama, reducing reliance on hosted LLM APIs.

## Technology Stack

- **Language:** Python, TypeScript, JavaScript
- **Backend:** FastAPI
- **Frontend:** React, Vite
- **LLM Runtime:** Ollama
- **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Reranker:** `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Database:** PostgreSQL with pgvector
- **Infrastructure:** Docker
- **Integration:** GitHub repositories

## Architecture

1. Connect to a GitHub repository.
2. Collect and process source files.
3. Split files into code chunks.
4. Generate vector embeddings.
5. Store chunks and embeddings in PostgreSQL with pgvector.
6. Retrieve and rerank relevant chunks for a user's question.
7. Generate an answer using the local language model.
8. Display the answer and related source references in the web interface.

## Prerequisites

- Python installed
- Node.js and npm installed
- Docker Desktop installed
- Ollama installed with the `qwen2.5:3b` model available

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/DevPilot-AI.git
cd DevPilot-AI
```

### 2. Set up the Python environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure the database

Start the PostgreSQL/pgvector service using the project's Docker Compose configuration.

Configure the database connection and password using environment variables. Never commit real credentials.

### 4. Start Ollama

```bash
ollama pull qwen2.5:3b
```

Make sure the Ollama service is running.

### 5. Start the backend

From the project root:

```powershell
$env:PYTHONPATH = "src"
uvicorn devpilot.api:app --reload --app-dir src
```

### 6. Start the frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL displayed by Vite in your terminal.

## Project Structure

```text
DevPilot-AI/
├── src/
│   └── devpilot/
│       ├── api.py
│       ├── assistant.py
│       ├── retriever.py
│       ├── embed_store.py
│       ├── chunker.py
│       └── github_connector.py
├── frontend/
├── data/
├── docker-compose.yml
├── requirements.txt
├── .gitignore
└── README.md
```

The exact files and folders may vary as development continues.

## Security

- Do not commit `.env` files, database passwords, API tokens, or other secrets.
- Keep virtual environments, generated datasets, caches, and build artifacts out of version control.
- Only index repositories you are authorized to access.

## Project Status

DevPilot AI is an actively developed portfolio project. Retrieval quality and answer accuracy may vary depending on the indexed repository and retrieved context.

## Future Improvements

- More reliable repository-level summaries
- Improved retrieval and context selection
- Better code navigation and dependency analysis
- Automated bug detection and code review
- Unit test generation
- Authentication and security analysis

## License

Choose a license before distributing or accepting external contributions.
