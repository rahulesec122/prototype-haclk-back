/**
 * API service for communicating with the Offline-First AI Assistant backend.
 */

const BASE_URL = import.meta.env?.VITE_API_URL || '';

/**
 * Check backend health status (Ollama / Gemini availability).
 */
export async function fetchHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
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
    const response = await fetch(`${BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId || undefined,
        stream: true,
      }),
      signal,
    });

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
