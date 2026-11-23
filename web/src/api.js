const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const MAX_HISTORY = 20; // the API rejects more than 20 earlier messages

/**
 * Ask the agent one question. `threadId` is the conversation to continue (null starts
 * one). `history` is the earlier turns, oldest first, as [{role: "user" | "assistant",
 * content}]: the server keeps the thread, and uses history only if it lost it (a restart).
 * Resolves to {answer, sources, tools, grades, threadId}.
 * Throws an Error whose message is safe to show the student.
 */
export async function askAgent(question, history, threadId = null) {
  let response;
  try {
    response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: history.slice(-MAX_HISTORY), thread_id: threadId }),
    });
  } catch {
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
    throw new Error(detail || "AggieFlow can't answer right now. Try again in a minute.");
  }
  const data = await response.json();
  return {
    answer: data.answer ?? "",
    sources: data.sources ?? [],
    tools: data.tools ?? [],
    grades: data.grades ?? [], // grade charts, one per course the agent looked up on anex.us
    threadId: data.thread_id ?? null,
  };
}
