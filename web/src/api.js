import { DefaultChatTransport } from "ai";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const MAX_HISTORY = 20; // the API rejects more than 20 earlier messages
const UNAVAILABLE = "AggieFlow can't answer right now. Try again in a minute.";

/**
 * useChat's transport to the API's /chat/stream (an AI SDK UI message stream). Each
 * request sends the latest question, the earlier answered turns as history, and
 * `getThreadId()`, the conversation to continue: the server keeps the thread and uses
 * history only if it lost it (a restart). Failures become Errors safe to show the student.
 */
export function chatTransport(getThreadId) {
  return new DefaultChatTransport({
    api: `${API_URL}/chat/stream`,
    fetch: studentSafeFetch,
    prepareSendMessagesRequest: ({ messages }) => ({
      body: {
        question: textOf(messages.at(-1)),
        history: historyOf(messages.slice(0, -1)).slice(-MAX_HISTORY),
        thread_id: getThreadId(),
      },
    }),
  });
}

/** A user message's text. */
export function textOf(message) {
  return (message?.parts ?? []).filter((p) => p.type === "text").map((p) => p.text).join("");
}

/** The checked answer the server sent at the end of an assistant message, or null. */
export function answerOf(message) {
  return message?.parts.find((p) => p.type === "data-answer")?.data.text ?? null;
}

/** Earlier turns that got an answer, as the API's history: oldest first. */
function historyOf(messages) {
  const history = [];
  messages.forEach((m, i) => {
    const answer = m.role === "user" ? answerOf(messages[i + 1]) : null;
    if (answer !== null) history.push({ role: "user", content: textOf(m) }, { role: "assistant", content: answer });
  });
  return history;
}

async function studentSafeFetch(url, init) {
  let response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    if (err?.name === "AbortError") throw err; // stopped on purpose ("New question")
    throw new Error("Can't reach AggieFlow right now. Check your connection and try again.");
  }
  if (!response.ok) {
    let detail = null;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail; // the API's 503 message
    } catch {
      // not JSON: use the generic message
    }
    if (response.status === 422) detail = "That question couldn't be sent. Try shortening it.";
    throw new Error(detail || UNAVAILABLE);
  }
  return response;
}
