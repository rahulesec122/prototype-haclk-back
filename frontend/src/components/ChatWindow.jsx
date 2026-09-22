import React, { useRef, useEffect } from 'react';
import ChatMessage from './ChatMessage';
import { Sparkles, Cpu, Cloud, Terminal } from 'lucide-react';

export default function ChatWindow({
  messages,
  onSampleClick,
}) {
  const bottomRef = useRef(null);

  // Auto-scroll on new tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center p-8 text-center max-w-2xl mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mb-4">
            <Sparkles className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">
            Offline-First AI Assistant
          </h2>
          <p className="text-sm text-slate-400 mb-8 max-w-md">
            Routes queries to local <strong className="text-emerald-400">Ollama (Qwen3)</strong> when available, and automatically falls back to <strong className="text-sky-400">Gemini API</strong> when offline.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
            <button
              onClick={() => onSampleClick("Explain Python in simple words")}
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/60 transition-all text-xs text-slate-300 flex items-start gap-3"
            >
              <Terminal className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-white mb-1">Explain Python in simple words</div>
                <div className="text-slate-400">Quick conceptual breakdown with minimal tokens</div>
              </div>
            </button>

            <button
              onClick={() => onSampleClick("What are the advantages of running LLMs locally offline?")}
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/60 transition-all text-xs text-slate-300 flex items-start gap-3"
            >
              <Cpu className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-white mb-1">Why run offline models?</div>
                <div className="text-slate-400">Privacy, zero cloud costs, and low local latency</div>
              </div>
            </button>

            <button
              onClick={() => onSampleClick("Write an async Python function to stream HTTP chunks with httpx")}
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/60 transition-all text-xs text-slate-300 flex items-start gap-3"
            >
              <Sparkles className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-white mb-1">Write an async streaming function</div>
                <div className="text-slate-400">Code generation test for the LLM</div>
              </div>
            </button>

            <button
              onClick={() => onSampleClick("How does the provider fallback work when Ollama fails?")}
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/60 transition-all text-xs text-slate-300 flex items-start gap-3"
            >
              <Cloud className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-white mb-1">How does fallback work?</div>
                <div className="text-slate-400">Learn about priority routing between providers</div>
              </div>
            </button>
          </div>
        </div>
      ) : (
        <div className="divide-y divide-slate-800/40">
          {messages.map((msg, index) => (
            <ChatMessage key={msg.id || index} message={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
