"use client";

import { useState, useEffect, useRef } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-research-agent-a166.onrender.com";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [job, setJob] = useState(null);
  const [report, setReport] = useState(null);
  const [progress, setProgress] = useState([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);
  const [elapsed, setElapsed] = useState(0);
  const [friendlyIdx, setFriendlyIdx] = useState(0);
  const eventSourceRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const elapsedRef = useRef(null);
  const friendlyMessages = [
    "Hold on — research is on the way 🔍",
    "Grab a coffee ☕ — we're digging through 10 sources",
    "Have a walk 🌿 — we're extracting evidence",
    "Almost there — checking citations ✨",
    "Brewing insights — synthesizing findings 🧪",
    "Hang tight — evaluating with Groq → Gemini fallback 🤖",
  ];

  // Elapsed timer + friendly rotation while running
  useEffect(() => {
    if (status === "running" || status === "pending") {
      setElapsed(0);
      setFriendlyIdx(0);
      elapsedRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
      const rot = setInterval(() => setFriendlyIdx((i) => (i + 1) % friendlyMessages.length), 4000);
      return () => {
        clearInterval(elapsedRef.current);
        clearInterval(rot);
      };
    } else {
      clearInterval(elapsedRef.current);
    }
  }, [status]);

  const submitResearch = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    // Clear previous polling/streaming
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    if (eventSourceRef.current) eventSourceRef.current.close();
    clearInterval(elapsedRef.current);
    setLoading(true);
    setError("");
    setReport(null);
    setProgress([]);
    setStatus("pending");
    setElapsed(0);
    setFriendlyIdx(0);

    try {
      const res = await fetch(`${API_URL}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setJob(data);
      setQuestion("");
      setStatus(data.status);
      pollStatus(data.id);
      streamProgress(data.id);
    } catch (err) {
      setError(err.message);
      setStatus("failed");
    } finally {
      setLoading(false);
    }
  };

  const pollStatus = (id) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/research/${id}`);
        if (!res.ok) return;
        const data = await res.json();
        setStatus(data.status);
        if (data.status === "completed") {
          clearInterval(interval);
          pollIntervalRef.current = null;
          fetchReport(id);
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
          }
        } else if (data.status === "failed") {
          clearInterval(interval);
          pollIntervalRef.current = null;
          setError("Research job failed — check Render logs for Groq/Tavily rate limits");
          if (eventSourceRef.current) eventSourceRef.current.close();
        }
      } catch {}
    }, 2000);
    pollIntervalRef.current = interval;
    setTimeout(() => {
      clearInterval(interval);
      if (pollIntervalRef.current === interval) pollIntervalRef.current = null;
    }, 180000);
  };

  const streamProgress = (id) => {
    if (eventSourceRef.current) eventSourceRef.current.close();
    const es = new EventSource(`${API_URL}/research/${id}/stream`);
    eventSourceRef.current = es;
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgress((prev) => [...prev, data]);
        if (data.progress) setStatus(data.progress);
        if (data.status === "completed" || data.progress === "completed") {
          es.close();
        }
      } catch {}
    };
    es.onerror = () => {
      // SSE may close, fallback to polling
    };
  };

  const fetchReport = async (id) => {
    try {
      const res = await fetch(`${API_URL}/research/${id}/report`);
      if (!res.ok) throw new Error("Report not yet available");
      const data = await res.json();
      setReport(data);
      setStatus("completed");
      // Add to history
      setHistory((prev) => [{ id, question: data.title || question, status: "completed", report: data }, ...prev].slice(0, 10));
    } catch (err) {
      setError(err.message);
    }
  };

  const openHistory = (item) => {
    setReport(item.report);
    setQuestion(item.question);
    setStatus(item.status);
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black text-zinc-900 dark:text-zinc-100">
      <header className="border-b bg-white dark:bg-zinc-900 dark:border-zinc-800">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold">AI Research Agent</h1>
          <a href={`${API_URL}/health`} target="_blank" className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300">API Health</a>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={submitResearch} className="bg-white dark:bg-zinc-900 rounded-xl border dark:border-zinc-800 p-6 space-y-4">
            <h2 className="font-medium">New Research</h2>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Does PostgreSQL support vector search? Explain pgvector, its main capabilities, and limitations."
              className="w-full min-h-[100px] rounded-lg border dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black dark:focus:ring-white"
              maxLength={2000}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-500">{question.length}/2000</span>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="rounded-full bg-black dark:bg-white text-white dark:text-black px-6 py-2 text-sm font-medium disabled:opacity-50 hover:bg-zinc-800 dark:hover:bg-zinc-200"
              >
                {loading ? "Starting..." : "Start Research"}
              </button>
            </div>
            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
            {status && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <span className={`inline-block h-2 w-2 rounded-full ${status === "completed" ? "bg-green-500" : status === "failed" ? "bg-red-500" : status === "running" ? "bg-blue-500 animate-pulse" : "bg-zinc-400"}`} />
                  <span className="capitalize">{status}</span>
                  {job && <span className="text-zinc-500 text-xs ml-2">{job.id.slice(0, 8)}...</span>}
                  {(status === "running" || status === "pending") && (
                    <span className="text-xs text-zinc-500 ml-auto">~{Math.max(0, 75 - elapsed)}s left • {elapsed}s elapsed</span>
                  )}
                </div>
                {(status === "running" || status === "pending") && (
                  <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900 p-3">
                    <p className="text-sm text-blue-900 dark:text-blue-200 animate-pulse">{friendlyMessages[friendlyIdx]}</p>
                    <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">Approx 60–90s • Tavily (10) + Groq → Gemini fallback • you’ll love the citations ✨</p>
                    <div className="mt-2 h-1.5 w-full bg-blue-100 dark:bg-blue-900 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-600 dark:bg-blue-400 transition-all duration-1000" style={{ width: `${Math.min(95, (elapsed / 75) * 100)}%` }} />
                    </div>
                  </div>
                )}
                {status === "completed" && <p className="text-sm text-green-700 dark:text-green-300">Done in {elapsed}s — report ready below ↓</p>}
              </div>
            )}
          </form>

          {(status === "running" || status === "pending") && job && (
            <div className="bg-white dark:bg-zinc-900 rounded-xl border dark:border-zinc-800 p-6 space-y-3">
              <h3 className="font-medium">In Progress</h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800 rounded-lg p-3">Researching: “{job.question}”</p>
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <span className="h-2 w-2 bg-blue-500 rounded-full animate-pulse" />
                <span>{progress.length > 0 ? progress[progress.length - 1]?.progress || "working..." : "starting..."}</span>
                <span className="ml-auto text-xs">{progress.length} steps</span>
              </div>
              {progress.length > 0 && (
                <div className="space-y-1 max-h-[150px] overflow-auto border-t dark:border-zinc-800 pt-3">
                  {progress.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-zinc-400">{i + 1}.</span>
                      <span>{p.progress || p.type}</span>
                      <span className="text-zinc-500 ml-auto">{p.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {progress.length > 0 && status !== "running" && status !== "pending" && (
            <div className="bg-white dark:bg-zinc-900 rounded-xl border dark:border-zinc-800 p-6">
              <h3 className="font-medium mb-3">Live Progress</h3>
              <div className="space-y-2 max-h-[200px] overflow-auto">
                {progress.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="text-zinc-400">{i + 1}.</span>
                    <span>{p.progress || p.type}</span>
                    <span className="text-zinc-500 text-xs ml-auto">{p.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report && (
            <div className="bg-white dark:bg-zinc-900 rounded-xl border dark:border-zinc-800 p-6 space-y-4">
              <div>
                <h2 className="text-lg font-semibold">{report.title}</h2>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2">{report.executive_summary}</p>
              </div>

              <div>
                <h3 className="font-medium">Key Findings</h3>
                <ul className="mt-2 space-y-3">
                  {report.key_findings?.map((f, i) => (
                    <li key={i} className="rounded-lg bg-zinc-50 dark:bg-zinc-800 p-3 text-sm">
                      <span className="font-medium">{i + 1}. {f.claim}</span>
                      <span className="ml-2 text-xs text-zinc-500">[{f.citation_ids?.join(", ")}]</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="font-medium">Detailed Analysis</h3>
                <p className="mt-2 text-sm leading-6 whitespace-pre-wrap">{report.detailed_analysis}</p>
              </div>

              {report.sources?.length > 0 && (
                <div>
                  <h3 className="font-medium">Sources</h3>
                  <ul className="mt-2 space-y-1">
                    {report.sources.map((s, i) => (
                      <li key={i} className="text-sm">
                        <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">
                          {s.title}
                        </a>
                        <span className="text-zinc-500 text-xs ml-2">{s.url}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {(report.limitations?.length > 0 || report.trade_offs?.length > 0) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  {report.limitations?.length > 0 && (
                    <div>
                      <h4 className="font-medium">Limitations</h4>
                      <ul className="list-disc list-inside text-zinc-600 dark:text-zinc-400 mt-1">
                        {report.limitations.map((l, i) => <li key={i}>{l}</li>)}
                      </ul>
                    </div>
                  )}
                  {report.trade_offs?.length > 0 && (
                    <div>
                      <h4 className="font-medium">Trade-offs</h4>
                      <ul className="list-disc list-inside text-zinc-600 dark:text-zinc-400 mt-1">
                        {report.trade_offs.map((t, i) => <li key={i}>{t}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <p className="text-sm text-zinc-600 dark:text-zinc-400 border-t dark:border-zinc-800 pt-3">{report.conclusion}</p>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="bg-white dark:bg-zinc-900 rounded-xl border dark:border-zinc-800 p-6">
            <h3 className="font-medium mb-3">Research History</h3>
            {history.length === 0 ? (
              <p className="text-sm text-zinc-500">No completed jobs yet.</p>
            ) : (
              <ul className="space-y-2">
                {history.map((h) => (
                  <li key={h.id} onClick={() => openHistory(h)} className="cursor-pointer rounded-lg border dark:border-zinc-700 p-3 hover:bg-zinc-50 dark:hover:bg-zinc-800">
                    <p className="text-sm font-medium truncate">{h.question}</p>
                    <p className="text-xs text-zinc-500 mt-1 capitalize">{h.status} • {h.id.slice(0, 8)}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>


        </div>
      </main>
    </div>
  );
}
