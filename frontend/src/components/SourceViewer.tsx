
import { useEffect, useState } from "react";
import {
  LoaderCircle,
  X,
  FileCode2,
  AlertCircle,
} from "lucide-react";

type SourceLine = {
  line_number: number;
  content: string;
};

type SourceFile = {
  repository: string;
  branch: string;
  file_path: string;
  lines: SourceLine[];
};

type SourceViewerProps = {
  filePath: string;
  startLine: number;
  endLine: number;
  repository: string;
  onClose: () => void;
};

export default function SourceViewer({
  filePath,
  startLine,
  endLine,
  repository,
  onClose,
}: SourceViewerProps) {
  const [source, setSource] = useState<SourceFile | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSource() {
      setLoading(true);
      setError("");
      setSource(null);

      try {
        const response = await fetch(
          `/api/source?file_path=${encodeURIComponent(filePath)}&repository=${encodeURIComponent(repository)}`,
          { signal: controller.signal }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail || "Unable to load source file."
          );
        }

        setSource(data);
      } catch (err) {
        if (
          err instanceof Error &&
          err.name !== "AbortError"
        ) {
          setError(err.message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadSource();

    return () => controller.abort();
  }, [filePath, repository]);

  const visibleLines =
    source?.lines.filter(
      (line) =>
        line.line_number >= Math.max(1, startLine - 5) &&
        line.line_number <= endLine + 5
    ) ?? [];

  return (
    <div className="source-overlay" onMouseDown={onClose}>
      <section
        className="source-viewer"
        role="dialog"
        aria-modal="true"
        aria-label={`Source code: ${filePath}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="source-viewer-header">
          <div className="source-viewer-title">
            <FileCode2 size={19} />

            <div>
              <strong>{filePath.split("/").pop()}</strong>
              <p>
                {source?.repository ?? repository} /{" "}
                {source?.branch ?? "Loading branch..."}
              </p>
            </div>
          </div>

          <button
            className="source-close"
            onClick={onClose}
            aria-label="Close source viewer"
          >
            <X size={19} />
          </button>
        </header>

        <div className="source-viewer-path">{filePath}</div>

        <div className="source-code">
          {loading && (
            <div className="source-state">
              <LoaderCircle className="spin" size={20} />
              Loading source code...
            </div>
          )}

          {!loading && error && (
            <div className="source-state source-error">
              <AlertCircle size={20} />
              {error}
            </div>
          )}

          {!loading &&
            !error &&
            visibleLines.map((line) => (
              <div
                className={`source-code-line ${
                  line.line_number >= startLine &&
                  line.line_number <= endLine
                    ? "highlighted"
                    : ""
                }`}
                key={line.line_number}
              >
                <span className="source-line-number">
                  {line.line_number}
                </span>
                <code>{line.content || " "}</code>
              </div>
            ))}
        </div>

        {!loading && !error && (
          <footer className="source-viewer-footer">
            Showing lines{" "}
            {visibleLines[0]?.line_number ?? 0}–
            {visibleLines[visibleLines.length - 1]?.line_number ?? 0}
            {" · "}
            Highlighted lines {startLine}–{endLine}
          </footer>
        )}
      </section>
    </div>
  );
}
