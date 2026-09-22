import React, { useState } from 'react';
import { User, Bot, Cpu, Cloud, ChevronDown, ChevronRight, Activity, Clock } from 'lucide-react';

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const [showTelemetry, setShowTelemetry] = useState(false);

  const provider = message.provider?.toLowerCase() || '';
  const isOllama = provider.includes('ollama');
  const isGemini = provider.includes('gemini');

  const latency = message.latency || {};
  const hasTelemetry = Object.keys(latency).length > 0;

  return (
    <div className={`py-4 px-6 flex gap-4 transition-colors ${isUser ? 'bg-slate-900/40' : 'bg-slate-800/30'}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
          isUser
            ? 'bg-slate-700 text-slate-200'
            : isOllama
            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            : isGemini
            ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
            : 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message Content */}
      <div className="flex-1 space-y-2 overflow-hidden">
        {/* Header row */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-300">
            {isUser ? 'You' : 'Assistant'}
          </span>

          {/* Provider Badge for Assistant */}
          {!isUser && message.provider && (
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${
                isOllama
                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                  : isGemini
                  ? 'bg-sky-500/10 text-sky-300 border-sky-500/20'
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              {isOllama ? (
                <>
                  <Cpu className="w-3 h-3 text-emerald-400" />
                  <span>Ollama (Local Qwen3)</span>
                </>
              ) : isGemini ? (
                <>
                  <Cloud className="w-3 h-3 text-sky-400" />
                  <span>Gemini (Online Fallback)</span>
                </>
              ) : (
                <span>{message.provider}</span>
              )}
            </span>
          )}

          {/* Fallback alert tag if switched to Gemini */}
          {!isUser && isGemini && (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded">
              Offline Fallback Triggered
            </span>
          )}
        </div>

        {/* Message Body */}
        <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap break-words">
          {message.content}
          {message.isStreaming && (
            <span className="inline-block w-2 h-4 bg-indigo-400 animate-pulse ml-0.5 align-middle" />
          )}
        </div>

        {/* Error message presentation */}
        {message.isError && (
          <div className="mt-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
            {message.content}
          </div>
        )}

        {/* Telemetry disclosure */}
        {!isUser && hasTelemetry && (
          <div className="pt-2">
            <button
              onClick={() => setShowTelemetry(!showTelemetry)}
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-300 font-mono transition-colors"
            >
              <Activity className="w-3.5 h-3.5 text-indigo-400" />
              <span>
                Telemetry: {latency.total_time_ms ? `${latency.total_time_ms}ms total` : 'view latency'}
              </span>
              {showTelemetry ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>

            {showTelemetry && (
              <div className="mt-2 p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Provider Decision</div>
                  <div className="font-semibold text-slate-200">
                    {latency.provider_selected ? `${latency.provider_selected} ms` : 'n/a'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">LLM Connected</div>
                  <div className="font-semibold text-slate-200">
                    {latency.llm_started ? `${latency.llm_started} ms` : 'n/a'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Time to 1st Token (TTFT)</div>
                  <div className="font-semibold text-emerald-400">
                    {latency.first_token ? `${latency.first_token} ms` : 'n/a'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Total Streaming Time</div>
                  <div className="font-semibold text-indigo-400">
                    {latency.total_time_ms ? `${latency.total_time_ms} ms` : 'n/a'}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
