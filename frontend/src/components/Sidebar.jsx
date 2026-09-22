import React from 'react';
import { Plus, MessageSquare, History, Database } from 'lucide-react';

export default function Sidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  isLoading,
}) {
  return (
    <aside className="w-72 border-r border-slate-800 bg-slate-950 flex flex-col h-[calc(100vh-4rem)]">
      {/* New Chat Button */}
      <div className="p-4 border-b border-slate-800/80">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium text-sm transition-all shadow-md shadow-indigo-600/20"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <History className="w-3.5 h-3.5" />
          <span>Recent Sessions</span>
        </div>

        {isLoading ? (
          <div className="px-3 py-4 text-xs text-slate-500 animate-pulse text-center">
            Loading conversations...
          </div>
        ) : conversations.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-slate-500">
            No saved conversations yet. Start a new chat!
          </div>
        ) : (
          conversations.map((conv) => {
            const isActive = conv.id === activeConversationId;
            const firstMsg = conv.messages?.find((m) => m.role === 'user');
            const previewText = firstMsg?.content || `Conversation ${conv.id.slice(0, 8)}`;
            const dateStr = conv.created_at
              ? new Date(conv.created_at).toLocaleDateString([], {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : '';

            return (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`w-full text-left p-3 rounded-xl transition-all flex flex-col gap-1 border ${
                  isActive
                    ? 'bg-slate-800/90 border-slate-700 text-white shadow-sm'
                    : 'border-transparent text-slate-400 hover:bg-slate-900 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center gap-2 w-full">
                  <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                  <span className="text-sm font-medium truncate flex-1">{previewText}</span>
                </div>
                {dateStr && <span className="text-[11px] text-slate-500 pl-5">{dateStr}</span>}
              </button>
            );
          })
        )}
      </div>

      {/* SQLite Footer */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/60 text-xs text-slate-500 flex items-center gap-2">
        <Database className="w-3.5 h-3.5 text-slate-400" />
        <span>Persisted in SQLite database</span>
      </div>
    </aside>
  );
}
