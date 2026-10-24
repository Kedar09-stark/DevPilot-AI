import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from devpilot.retriever import (
    list_repositories,
    get_repository_stats,
)
from devpilot.source_viewer import get_source_file

from devpilot.assistant import ask_devpilot

from devpilot.indexer import index_repository
from devpilot.github_connector import GitHubConnectorError


app = FastAPI(
    title="DevPilot AI",
    description="A repository-aware AI coding assistant",
    version="0.2.0",
)


class ConversationMessage(BaseModel):
    role: str
    content: str



class QuestionRequest(BaseModel):
    question: str
    history: list[ConversationMessage] = Field(default_factory=list)
    repository: str = "Kedar09-stark/Attend-AI"

class IndexRequest(BaseModel):
    url: str


class SourceReference(BaseModel):
    file_path: str
    start_line: int
    end_line: int


class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceReference]


class AnalysisRequest(BaseModel):
    repository: str = "Kedar09-stark/Attend-AI"
    focus: str = "general"


class AnalysisResponse(BaseModel):
    repository: str
    focus: str
    analysis: str
    sources: list[SourceReference]



@app.get("/repositories")
def get_repositories():
    try:
        return {"repositories": list_repositories()}
    except Exception as error:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list repositories: {error}",
        ) from error


@app.get("/stats")
def get_stats():
    try:
        return get_repository_stats()
    except Exception as error:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve repository stats: {error}",
        ) from error


@app.post("/index")
def index_github_repository(request: IndexRequest):
    url = request.url.strip()

    if not url:
        raise HTTPException(
            status_code=400,
            detail="GitHub repository URL cannot be empty.",
        )

    try:
        result = index_repository(url)
        return result

    except GitHubConnectorError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index repository: {error}",
        ) from error


@app.get("/health")
def health_check():
    return {"status": "ok", "app": "DevPilot AI"}



@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        history = [
            message.model_dump()
            for message in request.history
        ]

        result = ask_devpilot(
    question,
    history=history,
    repository=request.repository,
)

        return AnswerResponse(
            question=question,
            answer=result["answer"],
            sources=result["sources"],
        )

    except Exception as error:
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to answer question: {error}",
        ) from error

    


@app.get("/source")
def view_source(
    file_path: str,
    repository: str = "Kedar09-stark/Attend-AI",
):
    try:
        return get_source_file(file_path, repository)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error




@app.post("/analyze", response_model=AnalysisResponse)
def analyze_repository(request: AnalysisRequest):
    repository = request.repository.strip()
    focus = request.focus.strip().lower()

    allowed_focuses = {
        "general",
        "bugs",
        "security",
        "performance",
        "quality",
        "architecture",
    }

    if not repository:
        raise HTTPException(
            status_code=400,
            detail="Repository cannot be empty.",
        )

    if focus not in allowed_focuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid focus. Choose one of: {', '.join(sorted(allowed_focuses))}",
        )

    prompt = f"""
Analyze the indexed GitHub repository: {repository}.

Focus area: {focus}

Use the retrieved source code as evidence. Do not invent files,
code behavior, vulnerabilities, or bugs. If the available context
is insufficient, clearly state the limitation.

Organize the analysis using these headings:

## Summary
## Findings
## Limitations

Give specific explanations and refer to relevant files when possible.
"""

    try:
        result = ask_devpilot(
            prompt,
            history=[],
            repository=repository,
            limit=12,
        )

        return AnalysisResponse(
            repository=repository,
            focus=focus,
            analysis=result["answer"],
            sources=result["sources"],
        )

    except Exception as error:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze repository: {error}",
        ) from error
