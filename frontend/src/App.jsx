import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import ChatInput from './components/ChatInput';
import {
  fetchHealth,
  fetchConversations,
  fetchConversation,
  streamChatMessage,
} from './services/api';

export default function App() {
  const [health, setHealth] = useState({ status: 'unknown', ollama: false, gemini: false });
  const [isRefreshingHealth, setIsRefreshingHealth] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);

  const abortControllerRef = useRef(null);

  // Load health check on mount
  const checkHealth = async () => {
    setIsRefreshingHealth(true);
    try {
      const data = await fetchHealth();
      setHealth({
        status: data.status || 'healthy',
        ollama: Boolean(data.ollama),
        gemini: Boolean(data.gemini),
      });
    } catch (err) {
      console.warn('Backend unreachable:', err);
      setHealth({ status: 'unreachable', ollama: false, gemini: false });
    } finally {
      setIsRefreshingHealth(false);
    }
  };

  // Load conversations list on mount
  const loadConversations = async () => {
    try {
      setIsLoadingConversations(true);
      const data = await fetchConversations();
      setConversations(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoadingConversations(false);
    }
  };

  useEffect(() => {
    checkHealth();
    loadConversations();
    // Periodic health refresh every 30s
    const timer = setInterval(checkHealth, 30000);
    return () => clearInterval(timer);
  }, []);

  // Switch conversation
  const handleSelectConversation = async (convId) => {
    if (isStreaming) {
      abortControllerRef.current?.abort();
      setIsStreaming(false);
    }

    setActiveConversationId(convId);
    try {
      const convData = await fetchConversation(convId);
      setMessages(convData.messages || []);
    } catch (err) {
      console.error('Failed to switch conversation:', err);
    }
  };

  // Start new chat
  const handleNewChat = () => {
    if (isStreaming) {
      abortControllerRef.current?.abort();
      setIsStreaming(false);
    }
    setActiveConversationId(null);
    setMessages([]);
  };

  // Send message and stream response
  const handleSendMessage = async (userPrompt) => {
    const userMsg = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: userPrompt,
      created_at: new Date().toISOString(),
    };

    const assistantMsgPlaceholder = {
      id: `temp-assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      provider: '',
      isStreaming: true,
      latency: {},
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsgPlaceholder]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    await streamChatMessage({
      message: userPrompt,
      conversationId: activeConversationId,
      signal: controller.signal,
      onToken: (token) => {
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: updated[lastIdx].content + token,
            };
          }
          return updated;
        });
      },
      onComplete: ({ provider, conversation_id, latency }) => {
        setIsStreaming(false);
        if (conversation_id && conversation_id !== activeConversationId) {
          setActiveConversationId(conversation_id);
          loadConversations();
        }

        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              isStreaming: false,
              provider: provider,
              latency: latency,
            };
          }
          return updated;
        });
      },
      onError: (errMsg) => {
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              isStreaming: false,
              isError: true,
              content: errMsg,
            };
          }
          return updated;
        });
      },
    });
  };

  // Stop generation
  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
          updated[lastIdx] = {
            ...updated[lastIdx],
            isStreaming: false,
          };
        }
        return updated;
      });
    }
  };

  const allProvidersOffline = health.status !== 'unknown' && !health.ollama && !health.gemini;

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-900 text-slate-100 overflow-hidden">
      {/* Top Header */}
      <Header
        health={health}
        isRefreshing={isRefreshingHealth}
        onRefreshHealth={checkHealth}
      />

      {/* Main Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          isLoading={isLoadingConversations}
        />

        {/* Chat Area */}
        <main className="flex-1 flex flex-col h-full bg-slate-900 overflow-hidden relative">
          <ChatWindow
            messages={messages}
            onSampleClick={handleSendMessage}
          />
          <ChatInput
            onSendMessage={handleSendMessage}
            onStopStreaming={handleStopStreaming}
            isStreaming={isStreaming}
            disabled={isStreaming}
            allProvidersOffline={allProvidersOffline}
          />
        </main>
      </div>
    </div>
  );
}
