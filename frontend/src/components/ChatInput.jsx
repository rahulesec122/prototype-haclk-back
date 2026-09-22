import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, AlertCircle } from 'lucide-react';

export default function ChatInput({
  onSendMessage,
  onStopStreaming,
  isStreaming,
  disabled,
  allProvidersOffline,
}) {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!input.trim() || isStreaming || disabled) return;
    onSendMessage(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-4 border-t border-slate-800 bg-slate-900/90 backdrop-blur">
      {allProvidersOffline && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
          <span>
            Both Ollama and Gemini appear offline or unconfigured. You can still test sending a message to verify the fallback error handling.
          </span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="relative flex items-end gap-2 max-w-4xl mx-auto">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question or enter a prompt (e.g. 'Explain Python in simple words')..."
          disabled={disabled}
          rows={1}
          className="flex-1 max-h-40 min-h-[44px] bg-slate-950 border border-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 resize-none outline-none transition-all disabled:opacity-50"
        />

        {isStreaming ? (
          <button
            type="button"
            onClick={onStopStreaming}
            className="h-11 px-4 rounded-xl bg-rose-600 hover:bg-rose-500 active:bg-rose-700 text-white font-medium text-sm flex items-center justify-center gap-2 transition-all shadow-md shadow-rose-600/20 shrink-0"
            title="Stop generating"
          >
            <Square className="w-4 h-4 fill-white" />
            <span className="hidden sm:inline">Stop</span>
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            className="h-11 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-slate-800 disabled:text-slate-600 text-white font-medium text-sm flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-600/20 disabled:shadow-none shrink-0"
            title="Send message"
          >
            <Send className="w-4 h-4" />
            <span className="hidden sm:inline">Send</span>
          </button>
        )}
      </form>
    </div>
  );
}
