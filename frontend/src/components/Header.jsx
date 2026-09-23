import React from 'react';
import { Cpu, Cloud, RefreshCw, ShieldCheck, Zap } from 'lucide-react';

export default function Header({ health, isRefreshing, onRefreshHealth }) {
  const ollamaActive = health?.ollama ?? false;
  const geminiActive = health?.gemini ?? false;

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 flex items-center justify-between z-10">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <Zap className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
            Offline-First AI Assistant
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-800 text-slate-400 border border-slate-700">
              v0.1.0
            </span>
          </h1>
          <p className="text-xs text-slate-400">
            Local Ollama (Qwen) Primary • Gemini API Fallback
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Ollama Status Badge */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
            ollamaActive
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
          }`}
          title={ollamaActive ? 'Ollama server is active on localhost:11434' : 'Ollama is offline or unreachable'}
        >
          <Cpu className="w-3.5 h-3.5" />
          <span>{ollamaActive ? 'Ollama Available' : 'Ollama Unavailable'}</span>
          <span className={`w-2 h-2 rounded-full ${ollamaActive ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
        </div>

        {/* Gemini Status Badge */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
            geminiActive
              ? 'bg-sky-500/10 border-sky-500/30 text-sky-300'
              : 'bg-slate-800 border-slate-700 text-slate-400'
          }`}
          title={geminiActive ? 'Gemini API is configured & available' : 'Gemini fallback key is not set'}
        >
          <Cloud className="w-3.5 h-3.5" />
          <span>{geminiActive ? 'Gemini Available' : 'Gemini Offline'}</span>
          <span className={`w-2 h-2 rounded-full ${geminiActive ? 'bg-sky-400' : 'bg-slate-500'}`} />
        </div>

        {/* Refresh health check button */}
        <button
          onClick={onRefreshHealth}
          disabled={isRefreshing}
          className="p-2 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 transition-colors disabled:opacity-50"
          title="Refresh provider status"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-indigo-400' : ''}`} />
        </button>
      </div>
    </header>
  );
}
