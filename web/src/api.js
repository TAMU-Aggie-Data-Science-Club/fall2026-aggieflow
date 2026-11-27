const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const MAX_HISTORY = 20; // the API rejects more than 20 earlier messages

/**
 * Ask the agent one question. `threadId` is the conversation to continue (null starts
 * one). `history` is the earlier turns, oldest first, as [{role: "user" | "assistant",
 * content}]: the server keeps the thread, and uses history only if it lost it (a restart).
 * Resolves to {answer, sources, tools, steps, grades, threadId, asked}. `asked` is
 * {prompt, options} when the agent asks which one the student means; the reply (an
 * option or typed words) goes back as the next question in the same thread.
 * Throws an Error whose message is safe to show the student.
 */
export async function askAgent(question, history, threadId = null) {
  const response = await post("/chat", question, history, threadId);
  return toResult(await response.json());
}

/**
 * askAgent, streamed (#142): calls `onStep({name, args})` as the agent starts each lookup,
 * then resolves to the same result askAgent gives. Falls back to askAgent when the
 * server has no /chat/stream (an older API) or the browser can't read a stream.
 */
export async function askAgentStreaming(question, history, threadId = null, onStep = () => {}) {
  const response = await post("/chat/stream", question, history, threadId, true);
  if (!response || !response.body?.getReader) return askAgent(question, history, threadId);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    let chunk;
    try {
      chunk = await reader.read();
    } catch {
      throw new Error("The connection to AggieFlow dropped. Try again.");
    }
    if (chunk.done) break;
    buffer += chunk.value.replaceAll("\r\n", "\n");
    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const { event, data } = parseEvent(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
      if (event === "step") onStep(data);
      else if (event === "done") return toResult(data);
      else if (event === "error") throw new Error(data.detail || UNAVAILABLE);
    }
  }
  throw new Error("The connection to AggieFlow dropped. Try again.");
}

const UNAVAILABLE = "AggieFlow can't answer right now. Try again in a minute.";

/** One Server-Sent Event block -> {event, data}. */
function parseEvent(block) {
  let event = "message";
  const data = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  try {
    return { event, data: JSON.parse(data.join("\n")) };
  } catch {
    return { event: "ignored", data: null };
  }
}

/** POST a question. Throws a student-safe Error on failure. With `missingOk`, a 404
 * (no such endpoint on this server) resolves to null instead. */
async function post(path, question, history, threadId, missingOk = false) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: history.slice(-MAX_HISTORY), thread_id: threadId }),
    });
  } catch {
    throw new Error("Can't reach AggieFlow right now. Check your connection and try again.");
  }
  if (missingOk && (response.status === 404 || response.status === 405)) return null;
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

/** The API's JSON reply -> the result the UI uses. */
function toResult(data) {
  return {
    answer: data.answer ?? "",
    sources: data.sources ?? [],
    tools: data.tools ?? [],
    steps: data.steps ?? [], // each lookup the agent ran: {name, args, error}
    grades: data.grades ?? [], // grade charts, one per course the agent looked up on anex.us
    threadId: data.thread_id ?? null,
    asked: data.question ?? null, // not `question`: a turn's question is the student's text
  };
}
