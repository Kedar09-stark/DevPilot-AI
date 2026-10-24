
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCallback, useEffect, useState } from "react";
import SourceViewer from "./components/SourceViewer";
import {
  Bot,
  Code2,
  FolderGit2,
  MessageSquare,
  Plus,
  Send,
  Settings2,
  Sparkles,
  Terminal,
  LoaderCircle,
} from "lucide-react";
import "./App.css";

type SourceReference = {
  file_path: string;
  start_line: number;
  end_line: number;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[];
};

type RepositoryStats = {
  repository_count: number;
  total_chunks: number;
};

type AnalysisFocus =
  | "general"
  | "bugs"
  | "security"
  | "performance"
  | "quality"
  | "architecture";

type AnalysisResult = {
  repository: string;
  focus: AnalysisFocus;
  analysis: string;
  sources: SourceReference[];
};


type ActiveView = "assistant" | "repository" | "analysis" | "settings";

function App() {
  const [activeView, setActiveView] = useState<ActiveView>("assistant");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const [repositories, setRepositories] = useState<string[]>([]);
  const [repositoryStats, setRepositoryStats] =
    useState<RepositoryStats>({
      repository_count: 0,
      total_chunks: 0,
    });

  const [selectedRepository, setSelectedRepository] = useState(
    "Kedar09-stark/Attend-AI"
  );

  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState("");
  const [indexError, setIndexError] = useState("");
  const [repositoryError, setRepositoryError] = useState("");
  const [statsError, setStatsError] = useState("");
  const [selectedSource, setSelectedSource] =
    useState<SourceReference | null>(null);

  const [analysisFocus, setAnalysisFocus] =
  useState<AnalysisFocus>("general");

const [analysisResult, setAnalysisResult] =
  useState<AnalysisResult | null>(null);

const [isAnalyzing, setIsAnalyzing] = useState(false);
const [analysisError, setAnalysisError] = useState("");  

  // Fetch the latest repository statistics.
  const loadRepositoryStats = useCallback(async () => {
    try {
      const response = await fetch("/api/stats");

      if (!response.ok) {
        throw new Error("Failed to fetch repository statistics.");
      }

      const data: RepositoryStats = await response.json();

      setRepositoryStats(data);
      setStatsError("");
    } catch (error) {
      console.error("Stats error:", error);
      setStatsError("Repository statistics are unavailable.");
    }
  }, []);

  // Fetch the repositories indexed in the backend.
  const loadRepositories = useCallback(async () => {
    try {
      const response = await fetch("/api/repositories");

      if (!response.ok) {
        throw new Error("Failed to load repositories.");
      }

      const data: { repositories: string[] } =
        await response.json();

      setRepositories(data.repositories);
      setRepositoryError("");

      setSelectedRepository((current) => {
        if (data.repositories.includes(current)) {
          return current;
        }

        return data.repositories[0] ?? "";
      });

      if (data.repositories.length === 0) {
        setRepositoryError("No indexed repositories found.");
      }
    } catch (error) {
      console.error("Repository error:", error);
      setRepositoryError(
        "Could not load repositories. Check the backend."
      );
    }
  }, []);

  useEffect(() => {
    void loadRepositories();
    void loadRepositoryStats();
  }, [loadRepositories, loadRepositoryStats]);

  // Change repository and clear the previous conversation.
  function handleRepositoryChange(repository: string) {
    if (repository === selectedRepository) return;

    setSelectedRepository(repository);
    setMessages([]);
    setQuestion("");
    setSelectedSource(null);
  }

  // Index a public GitHub repository.
  async function handleIndexRepository(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const url = repositoryUrl.trim();

    if (!url || isIndexing) return;

    setIsIndexing(true);
    setIndexMessage("");
    setIndexError("");

    try {
      const response = await fetch("/api/index", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url }),
      });

      const data: {
        repository?: string;
        status?: string;
        chunks_indexed?: number;
        detail?: string;
      } = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || `Indexing failed: ${response.status}`
        );
      }

      // Refresh the dropdown and the statistics after indexing.
      await Promise.all([
        loadRepositories(),
        loadRepositoryStats(),
      ]);

      if (data.repository) {
        setSelectedRepository(data.repository);
        setMessages([]);
        setQuestion("");
        setSelectedSource(null);
      }

      setRepositoryUrl("");
      setIndexMessage(
        `Indexed ${data.repository ?? "repository"} successfully. ` +
          `${data.chunks_indexed ?? 0} code chunks stored.`
      );
    } catch (error) {
      setIndexError(
        error instanceof Error
          ? error.message
          : "An unexpected indexing error occurred."
      );
    } finally {
      setIsIndexing(false);
    }
  }

  // Submit a question to DevPilot AI.
  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (
      !trimmedQuestion ||
      isLoading ||
      !selectedRepository
    ) {
      return;
    }

    const conversationHistory = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessages((current) => [
      ...current,
      { role: "user", content: trimmedQuestion },
    ]);

    setQuestion("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          repository: selectedRepository,
          history: conversationHistory,
        }),
      });

      const data: {
        answer?: string;
        detail?: string;
        sources?: SourceReference[];
      } = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || `Request failed: ${response.status}`
        );
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer ?? "The API returned no answer.",
          sources: data.sources ?? [],
        },
      ]);
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "An unexpected error occurred.";

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            `I couldn't get an answer from the backend. ${errorMessage}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }


async function handleAnalyzeRepository() {
  if (!selectedRepository || isAnalyzing) return;

  setIsAnalyzing(true);
  setAnalysisError("");
  setAnalysisResult(null);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        repository: selectedRepository,
        focus: analysisFocus,
      }),
    });

    const data: {
      repository?: string;
      focus?: AnalysisFocus;
      analysis?: string;
      sources?: SourceReference[];
      detail?: string;
    } = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || `Analysis failed: ${response.status}`
      );
    }

    if (!data.analysis) {
      throw new Error("The backend returned no analysis.");
    }

    setAnalysisResult({
      repository: data.repository ?? selectedRepository,
      focus: data.focus ?? analysisFocus,
      analysis: data.analysis,
      sources: data.sources ?? [],
    });
  } catch (error) {
    setAnalysisError(
      error instanceof Error
        ? error.message
        : "An unexpected error occurred during analysis."
    );
  } finally {
    setIsAnalyzing(false);
  }
}


  function handleNewChat() {
    setMessages([]);
    setQuestion("");
    setSelectedSource(null);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Code2 size={22} />
          </div>
          <div>
            <h1>
              DevPilot<span> AI</span>
            </h1>
            <p>Developer workspace</p>
          </div>
        </div>

        <button className="new-chat" onClick={handleNewChat}>
          <Plus size={17} /> New conversation
        </button>

        <div className="sidebar-label">WORKSPACE</div>

        <button
          type="button"
          className={`nav-item ${activeView === "assistant" ? "active" : ""}`}
          onClick={() => setActiveView("assistant")}
        >
          <MessageSquare size={17} /> AI Assistant
        </button>

        <button
          type="button"
          className={`nav-item ${activeView === "repository" ? "active" : ""}`}
          onClick={() => setActiveView("repository")}
        >
          <FolderGit2 size={17} /> Repository
        </button>

        <button
          type="button"
          className={`nav-item ${activeView === "analysis" ? "active" : ""}`}
          onClick={() => setActiveView("analysis")}
        >
          <Terminal size={17} /> Code analysis
        </button>

        {/* Connected repository selector */}
        <div className="repo-card">
          <div className="repo-card-heading">
            <FolderGit2 size={17} />
            <span>CONNECTED REPOSITORY</span>
          </div>

          <select
            className="repo-sidebar-select"
            value={selectedRepository}
            onChange={(event) =>
              handleRepositoryChange(event.target.value)
            }
            disabled={repositories.length === 0 || isLoading}
            aria-label="Select repository"
          >
            {repositories.length === 0 && (
              <option value="">
                Loading repositories...
              </option>
            )}

            {repositories.map((repository) => (
              <option key={repository} value={repository}>
                {repository}
              </option>
            ))}
          </select>

          <div className="repo-status">
            <span className="status-dot" />
            Indexed code
          </div>

          {repositoryError && (
            <p className="repository-error">
              {repositoryError}
            </p>
          )}
        </div>

        {/* Add a new repository */}
        <div className="repo-card index-repo-card">
          <div className="repo-card-heading">
            <FolderGit2 size={17} />
            <span>ADD REPOSITORY</span>
          </div>

          <form onSubmit={handleIndexRepository}>
            <input
              className="repo-url-input"
              type="url"
              value={repositoryUrl}
              onChange={(event) =>
                setRepositoryUrl(event.target.value)
              }
              placeholder="https://github.com/owner/repo"
              aria-label="GitHub repository URL"
              required
              disabled={isIndexing}
            />

            <button
              className="index-repo-button"
              type="submit"
              disabled={!repositoryUrl.trim() || isIndexing}
            >
              {isIndexing ? (
                <>
                  <LoaderCircle className="spin" size={16} />
                  Indexing...
                </>
              ) : (
                <>
                  <Plus size={16} />
                  Index Repository
                </>
              )}
            </button>
          </form>

          {indexMessage && (
            <p className="repository-success">
              {indexMessage}
            </p>
          )}

          {indexError && (
            <p className="repository-error">
              {indexError}
            </p>
          )}
        </div>

        {/* Live repository statistics */}
        <div className="repo-stats">
          <div className="repo-stat">
            <span className="repo-stat-value">
              {repositoryStats.repository_count}
            </span>
            <span className="repo-stat-label">
              Repositories
            </span>
          </div>

          <div className="repo-stat">
            <span className="repo-stat-value">
              {repositoryStats.total_chunks.toLocaleString()}
            </span>
            <span className="repo-stat-label">
              Code chunks
            </span>
          </div>
        </div>

        {statsError && (
          <p className="repository-error">{statsError}</p>
        )}

        <div className="sidebar-bottom">
          <button
            type="button"
            className={`nav-item ${activeView === "settings" ? "active" : ""}`}
            onClick={() => setActiveView("settings")}
          >
            <Settings2 size={17} /> Settings
          </button>

          <div className="profile">
            <div className="avatar">DP</div>
            <div>
              <strong>DevPilot</strong>
              <p>Local AI workspace</p>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-panel">
        {activeView === "assistant" ? (
          <>
        <header className="topbar">
          <div>
            <div className="breadcrumb">
              Workspace <span>/</span> AI Assistant
            </div>
            <h2>Repository assistant</h2>
          </div>

          <div className="model-status">
            <span className="status-dot" /> Local model
          </div>
        </header>

        <section className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">
                <Sparkles size={26} />
              </div>

              <p className="eyebrow">
                YOUR AI CODING PARTNER
              </p>

              <h2>
                Understand your codebase.
                <br />
                <span>Build with confidence.</span>
              </h2>

              <p className="welcome-description">
                Ask questions about your repository and get
                explanations grounded in your code.
              </p>

              <div className="suggestion-grid">
                {[
                  "Summarize the project",
                  "What are the main apis ? ",
                  "Where is authentication handled?",
                  "Explain the project architecture",
                ].map((suggestion) => (
                  <button
                    className="suggestion"
                    key={suggestion}
                    onClick={() => setQuestion(suggestion)}
                  >
                    <Code2 size={17} />
                    <span>{suggestion}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((message, index) => (
                <div
                  className={`message ${message.role}`}
                  key={index}
                >
                  <div className="message-avatar">
                    {message.role === "user" ? (
                      "You"
                    ) : (
                      <Bot size={18} />
                    )}
                  </div>

                  <div className="message-content">
                    <p className="message-author">
                      {message.role === "user"
                        ? "You"
                        : "DevPilot AI"}
                    </p>

                    <div className="markdown-content">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                      >
                        {message.content}
                      </ReactMarkdown>
                    </div>

                    {message.role === "assistant" &&
                      message.sources &&
                      message.sources.length > 0 && (
                        <div className="sources-section">
                          <p className="sources-heading">
                            SOURCE REFERENCES
                          </p>

                          {message.sources.map(
                            (source, sourceIndex) => (
                              <button
                                type="button"
                                className="source-card"
                                key={`${source.file_path}-${source.start_line}-${sourceIndex}`}
                                onClick={() =>
                                  setSelectedSource(source)
                                }
                              >
                                <div className="source-icon">
                                  <Code2 size={16} />
                                </div>

                                <div className="source-details">
                                  <span className="source-path">
                                    {source.file_path}
                                  </span>
                                  <span className="source-lines">
                                    Lines {source.start_line}–
                                    {source.end_line}
                                  </span>
                                </div>
                              </button>
                            )
                          )}
                        </div>
                      )}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="demo-notice">
                  <LoaderCircle className="spin" size={16} />
                  DevPilot is thinking...
                </div>
              )}
            </div>
          )}
        </section>

        <footer className="composer-section">
          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              placeholder="Ask anything about your codebase..."
              rows={2}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey
                ) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />

            <div className="composer-footer">
              <span>
                <Code2 size={14} />
                {selectedRepository.split("/").pop() ||
                  "No repository selected"}
              </span>

              <button
                type="submit"
                disabled={
                  !question.trim() ||
                  isLoading ||
                  !selectedRepository
                }
                aria-label="Send question"
              >
                {isLoading ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <Send size={17} />
                )}
              </button>
            </div>
          </form>

          <p className="footer-note">
            DevPilot can make mistakes. Verify important code
            changes.
          </p>
        </footer>
          </>
        ) : activeView === "repository" ? (
          <>
            <header className="topbar">
              <div>
                <div className="breadcrumb">Workspace <span>/</span> Repository</div>
                <h2>Repository manager</h2>
              </div>
              <div className="model-status">
                <span className="status-dot" /> {repositories.length} indexed
              </div>
            </header>

            <section className="workspace-page">
              <div className="page-intro">
                <p className="eyebrow">YOUR CODEBASES</p>
                <h2>Repositories</h2>
                <p>Manage the GitHub repositories DevPilot has indexed and uses to answer code questions.</p>
              </div>

              {repositoryError && <p className="repository-error">{repositoryError}</p>}

              <div className="repository-summary-grid">
                <div className="repository-summary-card">
                  <span className="summary-icon"><FolderGit2 size={18} /></span>
                  <span className="repo-stat-label">Indexed repositories</span>
                  <strong>{repositoryStats.repository_count}</strong>
                </div>
                <div className="repository-summary-card">
                  <span className="summary-icon"><Code2 size={18} /></span>
                  <span className="repo-stat-label">Code chunks available for search</span>
                  <strong>{repositoryStats.total_chunks.toLocaleString()}</strong>
                </div>
              </div>

              <div className="repository-list-heading">
                <div>
                  <h3>Indexed repositories</h3>
                  <p>Select a repository to use it in AI Assistant.</p>
                </div>
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() => {
                    void loadRepositories();
                    void loadRepositoryStats();
                  }}
                >
                  Refresh list
                </button>
              </div>

              {repositories.length === 0 ? (
                <div className="empty-state">
                  <FolderGit2 size={28} />
                  <h3>No repositories found</h3>
                  <p>Use the Add Repository form in the sidebar to index a public GitHub repository.</p>
                </div>
              ) : (
                <div className="repository-list">
                  {repositories.map((repository) => (
                    <article className="repository-row" key={repository}>
                      <div className="repository-row-icon"><FolderGit2 size={20} /></div>
                      <div className="repository-row-details">
                        <strong>{repository}</strong>
                        <span><span className="status-dot" /> Indexed and ready for AI search</span>
                      </div>
                      <button
                        type="button"
                        className="secondary-action"
                        onClick={() => {
                          handleRepositoryChange(repository);
                          setActiveView("assistant");
                        }}
                      >
                        Use repository
                      </button>
                    </article>
                  ))}
                </div>
              )}

              <div className="repository-tip">
                <Sparkles size={18} />
                <div>
                  <strong>Want to add another codebase?</strong>
                  <p>Paste a public GitHub repository URL into the Add Repository box in the sidebar.</p>
                </div>
              </div>
            </section>
          </>
        
) : activeView === "analysis" ? (
  <>
    <header className="topbar">
      <div>
        <div className="breadcrumb">
          Workspace <span>/</span> Code analysis
        </div>
        <h2>Code analysis</h2>
      </div>

      <div className="model-status">
        <span className="status-dot" />
        {isAnalyzing ? "Analyzing repository..." : "Ready to analyze"}
      </div>
    </header>

    <section className="workspace-page">
      <div className="page-intro">
        <p className="eyebrow">UNDERSTAND YOUR CODE</p>
        <h2>Repository analysis</h2>
        <p>
          Review your indexed codebase for potential issues and
          understand its architecture using DevPilot AI.
        </p>
      </div>

      <div className="feature-card">
        <span className="summary-icon">
          <Terminal size={20} />
        </span>

        <h3>Configure analysis</h3>

        <p>
          Repository:{" "}
          <strong>
            {selectedRepository || "No repository selected"}
          </strong>
        </p>

        <label htmlFor="analysis-focus">Analysis focus</label>

        <select
          id="analysis-focus"
          className="repo-url-input"
          value={analysisFocus}
          onChange={(event) =>
            setAnalysisFocus(event.target.value as AnalysisFocus)
          }
          disabled={isAnalyzing}
        >
          <option value="general">General overview</option>
          <option value="bugs">Potential bugs</option>
          <option value="security">Security concerns</option>
          <option value="performance">Performance</option>
          <option value="quality">Code quality</option>
          <option value="architecture">Architecture</option>
        </select>

        <button
          type="button"
          className="primary-action"
          disabled={!selectedRepository || isAnalyzing}
          onClick={() => void handleAnalyzeRepository()}
        >
          {isAnalyzing ? (
            <>
              <LoaderCircle className="spin" size={16} />
              Analyzing...
            </>
          ) : (
            <>
              <Sparkles size={16} />
              Analyze repository
            </>
          )}
        </button>
      </div>

      {analysisError && (
        <div className="analysis-error">
          <strong>Analysis failed</strong>
          <p>{analysisError}</p>
          <p>
            Check that the backend is running and the selected
            repository is indexed.
          </p>
        </div>
      )}

      {isAnalyzing && (
        <div className="empty-state">
          <LoaderCircle className="spin" size={26} />
          <h3>Reviewing your codebase</h3>
          <p>
            DevPilot is retrieving relevant code and generating
            its analysis. This may take a little while.
          </p>
        </div>
      )}

      {analysisResult && !isAnalyzing && (
        <div className="analysis-results">
          <div className="repository-list-heading">
            <div>
              <h3>Analysis results</h3>
              <p>
                {analysisResult.repository} ·{" "}
                {analysisResult.focus}
              </p>
            </div>

            <button
              type="button"
              className="secondary-action"
              onClick={() => setAnalysisResult(null)}
            >
              Clear results
            </button>
          </div>

          <div className="analysis-result-content markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {analysisResult.analysis}
            </ReactMarkdown>
          </div>

          {analysisResult.sources.length > 0 && (
            <div className="sources-section">
              <p className="sources-heading">
                SOURCE REFERENCES
              </p>

              {analysisResult.sources.map((source, index) => (
                <button
                  type="button"
                  className="source-card"
                  key={`${source.file_path}-${source.start_line}-${index}`}
                  onClick={() => setSelectedSource(source)}
                >
                  <div className="source-icon">
                    <Code2 size={16} />
                  </div>

                  <div className="source-details">
                    <span className="source-path">
                      {source.file_path}
                    </span>
                    <span className="source-lines">
                      Lines {source.start_line}–{source.end_line}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}

          <p className="page-disclaimer">
            AI-generated findings may be incomplete. Verify important
            issues against the source code.
          </p>
        </div>
      )}
    </section>
  </>
) : (

          <>
            <header className="topbar">
              <div>
                <div className="breadcrumb">Workspace <span>/</span> Settings</div>
                <h2>Settings</h2>
              </div>
              <div className="model-status"><span className="status-dot" /> Local workspace</div>
            </header>
            <section className="workspace-page">
              <div className="page-intro">
                <p className="eyebrow">PREFERENCES</p>
                <h2>Settings</h2>
                <p>Workspace information and current configuration.</p>
              </div>
              <div className="settings-list">
                <div className="settings-row">
                  <div><strong>AI model</strong><p>Local Ollama model configured by the backend</p></div>
                  <span className="settings-value">Local model</span>
                </div>
                <div className="settings-row">
                  <div><strong>Vector database</strong><p>PostgreSQL with pgvector, used for code retrieval</p></div>
                  <span className="settings-value">Configured in backend</span>
                </div>
                <div className="settings-row">
                  <div><strong>Indexed repositories</strong><p>Repositories currently available to DevPilot</p></div>
                  <span className="settings-value">{repositoryStats.repository_count}</span>
                </div>
                <div className="settings-row">
                  <div><strong>Indexed code chunks</strong><p>Code segments available for semantic search</p></div>
                  <span className="settings-value">{repositoryStats.total_chunks.toLocaleString()}</span>
                </div>
              </div>
              <p className="page-disclaimer">These are informational settings for now. Model and database configuration remain in the backend environment.</p>
            </section>
          </>
        )}
      </main>

      {selectedSource && (
        <SourceViewer
  filePath={selectedSource.file_path}
  startLine={selectedSource.start_line}
  endLine={selectedSource.end_line}
  repository={selectedRepository}
  onClose={() => setSelectedSource(null)}
/>
        
      )}
    </div>
  );
}

export default App;
