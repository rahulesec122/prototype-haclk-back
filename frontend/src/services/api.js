/**
 * API service for communicating with the Offline-First AI Assistant backend.
 */

const getBaseUrl = () => {
  const envUrl = import.meta.env?.VITE_API_URL;
  if (envUrl && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  return 'http://127.0.0.1:8001';
};

const BASE_URL = getBaseUrl();

/**
 * Check backend health status (Ollama / Gemini availability).
 * Resiliently checks configured base URL, proxy path, and direct backend.
 */
export async function fetchHealth() {
  const candidates = [
    `${BASE_URL}/health`,
    '/health',
    'http://127.0.0.1:8001/health',
    'http://localhost:8001/health',
  ];
  const uniqueUrls = [...new Set(candidates.filter(Boolean))];

  for (const url of uniqueUrls) {
    try {
      const res = await fetch(url, { method: 'GET' });
      if (res.ok) {
        return await res.json();
      }
    } catch (_) {
      // Continue to next candidate
    }
  }

  throw new Error('Backend health check failed on all endpoints');
}

/**
 * Fetch all stored conversations.
 */
export async function fetchConversations() {
  const res = await fetch(`${BASE_URL}/api/conversations`);
  if (!res.ok) {
    throw new Error(`Failed to load conversations: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Fetch details and message history for a specific conversation.
 */
export async function fetchConversation(id) {
  const res = await fetch(`${BASE_URL}/api/conversations/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to load conversation ${id}: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Stream a chat response from /api/chat using Server-Sent Events.
 *
 * @param {Object} options
 * @param {string} options.message - User prompt
 * @param {string|null} options.conversationId - Conversation UUID
 * @param {function(string): void} options.onToken - Called for each token chunk
 * @param {function({provider: string, conversation_id: string, latency: Object}): void} options.onComplete - Called upon stream completion
 * @param {function(string): void} options.onError - Called on error
 * @param {AbortSignal} [options.signal] - Optional abort signal to cancel generation
 */
export async function streamChatMessage({
  message,
  conversationId = null,
  onToken,
  onComplete,
  onError,
  signal,
}) {
  try {
    const candidates = [
      `${BASE_URL}/api/chat`,
      '/api/chat',
      'http://127.0.0.1:8001/api/chat',
      'http://localhost:8001/api/chat',
    ];
    const uniqueUrls = [...new Set(candidates.filter(Boolean))];

    const bodyPayload = JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
      stream: true,
    });

    let response = null;
    let lastNetworkErr = null;

    for (const url of uniqueUrls) {
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: bodyPayload,
          signal,
        });
        response = res;
        break;
      } catch (fetchErr) {
        if (fetchErr.name === 'AbortError') throw fetchErr;
        lastNetworkErr = fetchErr;
      }
    }

    if (!response) {
      throw lastNetworkErr || new Error('Unable to connect to chat endpoint');
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const errorMsg = errData.detail || `Request failed with status ${response.status}`;
      onError(errorMsg);
      return;
    }

    const providerHeader = response.headers.get('X-Provider-Used');
    const conversationIdHeader = response.headers.get('X-Conversation-Id');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep partial line in buffer

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;

        const payloadStr = trimmed.slice(5).trim();
        try {
          const data = JSON.parse(payloadStr);

          if (data.type === 'token') {
            onToken(data.content);
          } else if (data.type === 'complete') {
            onComplete({
              provider: data.provider || providerHeader || 'unknown',
              conversation_id: data.conversation_id || conversationIdHeader,
              latency: data.latency || {},
            });
          } else if (data.type === 'error') {
            onError(data.message || 'An error occurred during inference.');
          }
        } catch (jsonErr) {
          console.warn('Failed to parse SSE line:', trimmed, jsonErr);
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('Stream generation aborted by user.');
    } else {
      onError(err.message || 'Failed to connect to the assistant server.');
    }
  }
}
