import { useState } from "react";
import { api, messageFromError } from "../api/client";

export default function Chat() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! Ask me about published events, your timetable, or Lost & Found. I’ll tell you when I don’t have a verified answer." },
  ]);
  const [text, setText] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [busy, setBusy] = useState(false);
  const send = async (event) => {
    event.preventDefault();
    const question = text.trim();
    if (!question || busy) return;
    setMessages((items) => [...items, { role: "user", content: question }]);
    setText("");
    setBusy(true);
    try {
      const { data } = await api.post("/chat/message", { message: question, conversation_id: conversationId });
      setConversationId(data.conversation_id);
      setMessages((items) => [...items, { role: "assistant", content: data.reply }]);
    } catch (error) {
      setMessages((items) => [...items, { role: "assistant", content: messageFromError(error) }]);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="page chat-page">
      <header className="page-header"><div><p className="eyebrow">CAMPUS ASSISTANT</p><h1>Ask Campus Pilot</h1>
        <p className="muted">Answers are grounded in data published by your college.</p></div></header>
      <section className="card chat-card" aria-label="Conversation">
        <div className="messages" aria-live="polite">{messages.map((message, index) =>
          <div className={`message ${message.role}`} key={`${index}-${message.role}`}>
            <span className="message-label">{message.role === "assistant" ? "CAMPUS PILOT" : "YOU"}</span>
            <p>{message.content}</p>
          </div>)}
          {busy && <p className="muted typing">Campus Pilot is checking…</p>}
        </div>
        <form className="chat-form" onSubmit={send}>
          <label className="sr-only" htmlFor="chat-input">Your message</label>
          <input id="chat-input" value={text} onChange={(event) => setText(event.target.value)}
            placeholder="Ask a campus question…" maxLength={4000} />
          <button className="button button-primary" disabled={busy || !text.trim()}>Send</button>
        </form>
      </section>
    </div>
  );
}
