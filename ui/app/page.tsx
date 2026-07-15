"use client";

import { useState, useRef, useEffect } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production"
    ? "https://uslexragsystem-production.up.railway.app"
    : "http://localhost:8000");

interface Citation {
  doc_name: string;
  page_number: number;
  chunk_text_snippet: string;
  _flag?: string;
}

interface AskResponse {
  query: string;
  query_type: string;
  answer: string;
  verified_citations: Citation[];
  flagged_citations: Citation[];
  retrieved_chunks: { chunk_id: string; doc_title: string; page_number: number; text: string }[];
}

const QUERY_TYPE_COLORS: Record<string, string> = {
  factual: "bg-blue-900/40 text-blue-300 border-blue-700/40",
  interpretive: "bg-purple-900/40 text-purple-300 border-purple-700/40",
  multi_hop: "bg-amber-900/40 text-amber-300 border-amber-700/40",
  out_of_scope: "bg-red-900/40 text-red-300 border-red-700/40",
};

const SAMPLE_QUERIES = [
  "What does IRC Section 501 say about exempt organizations?",
  "What is the corporate bond monthly yield curve for 2026?",
  "How should Section 7463 be interpreted for small tax cases?",
  "What are the tax filing deadlines for small businesses?",
  "Compare IRS notice provisions with IRC sections on interest rates.",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedCitations, setExpandedCitations] = useState(false);
  const [expandedChunks, setExpandedChunks] = useState(false);
  const [topK, setTopK] = useState(8);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async (q?: string) => {
    const queryText = q || query;
    if (!queryText.trim()) return;

    setLoading(true);
    setResult(null);
    setError(null);
    setExpandedCitations(false);
    setExpandedChunks(false);

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryText, top_k: topK }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const data: AskResponse = await res.json();
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reach the backend. Is it running?");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [query]);

  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-white/5 sticky top-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-yellow-500 to-amber-700 flex items-center justify-center text-sm font-bold shadow-lg">
              ⚖
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">LexRAG</h1>
              <p className="text-xs text-gray-500">US Tax & Legal Research Assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse-slow"></div>
            <span className="text-xs text-gray-400">System Online</span>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Hero */}
        {!result && !loading && (
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 glass rounded-full px-4 py-2 text-xs text-amber-400 border border-amber-800/30 mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse-slow"></span>
              Hybrid Search · Verified Citations · Two-Pass Verification
            </div>
            <h2 className="text-4xl font-bold text-white mb-4 leading-tight">
              Ask Anything About<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-yellow-600">
                US Tax & Legal Law
              </span>
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              Every answer comes with exact, verifiable citations — document name and page number.
              Hallucinated citations are automatically detected and flagged.
            </p>
          </div>
        )}

        {/* Search Box */}
        <div className="glass rounded-2xl p-1 mb-6 gold-glow">
          <div className="flex flex-col gap-2 p-4">
            <textarea
              ref={textareaRef}
              id="query-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a legal or tax question... (Ctrl+Enter to submit)"
              rows={2}
              className="w-full bg-transparent text-white placeholder-gray-600 resize-none outline-none text-base leading-relaxed"
            />
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <label className="text-xs text-gray-500">Results:</label>
                <select
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="bg-white/5 border border-white/10 text-gray-300 text-xs rounded-lg px-2 py-1 outline-none"
                >
                  {[5, 8, 10, 15].map((k) => (
                    <option key={k} value={k}>{k}</option>
                  ))}
                </select>
              </div>
              <button
                id="submit-btn"
                onClick={() => handleSubmit()}
                disabled={loading || !query.trim()}
                className="flex items-center gap-2 bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold px-5 py-2 rounded-xl transition-all duration-200 shadow-lg hover:shadow-amber-900/30"
              >
                {loading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                    Researching...
                  </>
                ) : (
                  <>Search ↵</>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Sample Queries */}
        {!result && !loading && (
          <div className="mb-12">
            <p className="text-xs text-gray-600 mb-3">Try a sample query:</p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_QUERIES.map((q, i) => (
                <button
                  key={i}
                  onClick={() => { setQuery(q); handleSubmit(q); }}
                  className="text-xs glass glass-hover rounded-full px-3 py-1.5 text-gray-400 border border-white/5 cursor-pointer"
                >
                  {q.substring(0, 50)}...
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="glass rounded-xl p-4 border border-red-800/40 bg-red-900/10 mb-6">
            <p className="text-red-400 text-sm">⚠ {error}</p>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="glass rounded-xl p-5 animate-pulse">
                <div className="h-3 bg-white/5 rounded w-1/4 mb-3"></div>
                <div className="space-y-2">
                  <div className="h-3 bg-white/5 rounded w-full"></div>
                  <div className="h-3 bg-white/5 rounded w-5/6"></div>
                  <div className="h-3 bg-white/5 rounded w-4/6"></div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Query Type Badge + Query */}
            <div className="flex items-center gap-3 mb-2">
              <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${QUERY_TYPE_COLORS[result.query_type] || "bg-gray-900 text-gray-400 border-gray-700"}`}>
                {result.query_type.replace("_", " ").toUpperCase()}
              </span>
              <span className="text-gray-500 text-xs">"{result.query}"</span>
            </div>

            {/* Answer */}
            <div className="glass rounded-2xl p-6 border border-amber-900/20">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-amber-500 text-sm">⚖</span>
                <h3 className="text-sm font-semibold text-amber-400 uppercase tracking-wider">Answer</h3>
              </div>
              {result.answer === "INSUFFICIENT_CONTEXT" ? (
                <div className="text-gray-400 italic">
                  The provided legal documents do not contain sufficient information to answer this question.
                </div>
              ) : (
                <p className="text-gray-100 leading-relaxed whitespace-pre-wrap">{result.answer}</p>
              )}
            </div>

            {/* Verified Citations */}
            {result.verified_citations.length > 0 && (
              <div className="glass rounded-2xl border border-green-900/30 overflow-hidden">
                <button
                  onClick={() => setExpandedCitations(!expandedCitations)}
                  className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/3 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-green-500">✓</span>
                    <h3 className="text-sm font-semibold text-green-400">
                      Verified Citations ({result.verified_citations.length})
                    </h3>
                    <span className="text-xs text-gray-600">— independently confirmed against source pages</span>
                  </div>
                  <span className="text-gray-500 text-sm">{expandedCitations ? "▲" : "▼"}</span>
                </button>

                {expandedCitations && (
                  <div className="border-t border-green-900/20 divide-y divide-white/5">
                    {result.verified_citations.map((cit, i) => (
                      <div key={i} className="px-6 py-4 hover:bg-white/2 transition-colors">
                        <div className="flex items-start gap-3">
                          <span className="text-green-600 text-xs mt-0.5 shrink-0">#{i + 1}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                              <span className="text-xs font-semibold text-white truncate">{cit.doc_name}</span>
                              <span className="text-xs glass rounded px-2 py-0.5 text-amber-400 border border-amber-900/30 shrink-0">
                                Page {cit.page_number}
                              </span>
                            </div>
                            {cit.chunk_text_snippet && (
                              <p className="text-xs text-gray-500 italic line-clamp-3">
                                "{cit.chunk_text_snippet}"
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Flagged Citations */}
            {result.flagged_citations.length > 0 && (
              <div className="glass rounded-2xl border border-red-900/30 overflow-hidden">
                <div className="flex items-center gap-2 px-6 py-4">
                  <span className="text-red-500">⚠</span>
                  <h3 className="text-sm font-semibold text-red-400">
                    Flagged Citations ({result.flagged_citations.length})
                  </h3>
                  <span className="text-xs text-gray-600">— hallucinated, stripped from answer</span>
                </div>
                <div className="border-t border-red-900/20 px-6 py-3 space-y-2">
                  {result.flagged_citations.map((cit, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-red-600">✗</span>
                      <span className="text-red-400/70">{cit.doc_name} — Page {cit.page_number}</span>
                      <span className="text-gray-600">({cit._flag})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Retrieved Chunks (Collapsible) */}
            {result.retrieved_chunks.length > 0 && (
              <div className="glass rounded-2xl border border-white/5 overflow-hidden">
                <button
                  onClick={() => setExpandedChunks(!expandedChunks)}
                  className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/3 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500">📄</span>
                    <h3 className="text-sm font-medium text-gray-400">
                      Retrieved Context ({result.retrieved_chunks.length} chunks)
                    </h3>
                  </div>
                  <span className="text-gray-500 text-sm">{expandedChunks ? "▲" : "▼"}</span>
                </button>
                {expandedChunks && (
                  <div className="border-t border-white/5 divide-y divide-white/5">
                    {result.retrieved_chunks.map((chunk, i) => (
                      <div key={i} className="px-6 py-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-amber-600 font-medium">{chunk.doc_title}</span>
                          <span className="text-xs text-gray-600">· Page {chunk.page_number}</span>
                        </div>
                        <p className="text-xs text-gray-600 line-clamp-2">{chunk.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* New Query Button */}
            <div className="text-center pt-4">
              <button
                onClick={() => { setResult(null); setQuery(""); setError(null); }}
                className="text-sm text-gray-500 hover:text-amber-400 transition-colors"
              >
                ← New Question
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-white/5 mt-16 py-6">
        <div className="max-w-6xl mx-auto px-6 text-center text-xs text-gray-700">
          LexRAG · Hybrid RAG with ChromaDB + BM25 + RRF · Claude-powered with two-pass citation verification
        </div>
      </footer>
    </main>
  );
}
