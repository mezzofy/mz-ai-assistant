import { useState, useEffect, useRef } from "react";

// ─── Mezzofy Brand System ───
const BRAND = {
  primary: "#0A1628",
  secondary: "#1B2B44",
  accent: "#00D4AA",
  accentGlow: "rgba(0,212,170,0.15)",
  accentSoft: "#00D4AA22",
  surface: "#0F1F35",
  surfaceLight: "#162A45",
  card: "#1A2F4D",
  border: "#1E3A5F",
  text: "#E8F0F8",
  textMuted: "#7A8FA6",
  textDim: "#4A6280",
  white: "#FFFFFF",
  danger: "#FF4B6E",
  warning: "#FFB84D",
  success: "#00D4AA",
  info: "#4DA6FF",
  deptColors: {
    finance: "#FFB84D",
    sales: "#00D4AA",
    marketing: "#C77DFF",
    support: "#4DA6FF",
    management: "#FF6B8A",
  },
};

// ─── Icons (SVG Components) ───
const Icon = ({ name, size = 20, color = BRAND.textMuted }) => {
  const icons = {
    chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
    send: <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />,
    image: <><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" /></>,
    video: <><rect x="2" y="2" width="20" height="20" rx="2.18" /><path d="m7 2 0 20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5" /></>,
    camera: <><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></>,
    mic: <><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></>,
    audio: <><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><line x1="10" y1="9" x2="8" y2="9" /></>,
    globe: <><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></>,
    files: <><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></>,
    back: <><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></>,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></>,
    check: <polyline points="20 6 9 17 4 12" />,
    clock: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>,
    user: <><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></>,
    lock: <><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></>,
    eye: <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></>,
    sparkle: <><path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" /></>,
    pdf: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>,
    pptx: <><rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></>,
    history: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>,
    plus: <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>,
    search: <><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></>,
    chevron: <polyline points="9 18 15 12 9 6" />,
    bell: <><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
    logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></>,
    stop: <rect x="3" y="3" width="18" height="18" rx="2" />,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {icons[name]}
    </svg>
  );
};

// ─── Department Badge ───
const DeptBadge = ({ dept, compact }) => (
  <span style={{
    background: BRAND.deptColors[dept] + "18",
    color: BRAND.deptColors[dept],
    padding: compact ? "2px 8px" : "4px 12px",
    borderRadius: 20,
    fontSize: compact ? 10 : 11,
    fontWeight: 700,
    letterSpacing: "0.5px",
    textTransform: "uppercase",
    border: `1px solid ${BRAND.deptColors[dept]}33`,
  }}>
    {dept}
  </span>
);

// ─── Mobile Frame ───
const PhoneFrame = ({ children, title }) => (
  <div style={{
    width: 390, minHeight: 780, background: BRAND.primary,
    borderRadius: 40, border: `2px solid ${BRAND.border}`,
    overflow: "hidden", position: "relative",
    boxShadow: `0 20px 80px rgba(0,0,0,0.6), 0 0 0 1px ${BRAND.border}, inset 0 1px 0 ${BRAND.surfaceLight}`,
    display: "flex", flexDirection: "column",
  }}>
    {/* Status Bar */}
    <div style={{
      height: 54, display: "flex", alignItems: "flex-end", justifyContent: "space-between",
      padding: "0 28px 6px", fontSize: 14, fontWeight: 600, color: BRAND.text,
    }}>
      <span>9:41</span>
      <div style={{ width: 126, height: 32, background: "#000", borderRadius: 20, position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)" }} />
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <div style={{ width: 16, height: 10, border: `1.5px solid ${BRAND.text}`, borderRadius: 2, position: "relative" }}>
          <div style={{ position: "absolute", right: 1, top: 1, bottom: 1, left: 3, background: BRAND.accent, borderRadius: 1 }} />
        </div>
      </div>
    </div>
    {children}
  </div>
);

// ─── Tab Bar ───
const TabBar = ({ active, onNav }) => {
  const tabs = [
    { id: "chat", icon: "chat", label: "Chat" },
    { id: "history", icon: "history", label: "History" },
    { id: "files", icon: "files", label: "Files" },
    { id: "settings", icon: "settings", label: "Settings" },
  ];
  return (
    <div style={{
      display: "flex", borderTop: `1px solid ${BRAND.border}`, background: BRAND.surface,
      padding: "8px 0 26px", flexShrink: 0,
    }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onNav(t.id)} style={{
          flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
          background: "none", border: "none", cursor: "pointer", padding: "6px 0",
        }}>
          <Icon name={t.icon} size={22} color={active === t.id ? BRAND.accent : BRAND.textDim} />
          <span style={{
            fontSize: 10, fontWeight: active === t.id ? 700 : 500,
            color: active === t.id ? BRAND.accent : BRAND.textDim,
            letterSpacing: "0.3px",
          }}>{t.label}</span>
        </button>
      ))}
    </div>
  );
};

// ════════════════════════════════════════
// ═══ LOGIN SCREEN
// ════════════════════════════════════════
const LoginScreen = ({ onLogin }) => {
  const [email, setEmail] = useState("sarah@mezzofy.com");
  const [pass, setPass] = useState("••••••••");
  const [loading, setLoading] = useState(false);

  const handleLogin = () => {
    setLoading(true);
    setTimeout(() => onLogin(), 1200);
  };

  return (
    <PhoneFrame>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 32px" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div style={{
            width: 72, height: 72, borderRadius: 20, margin: "0 auto 20px",
            background: `linear-gradient(135deg, ${BRAND.accent}, ${BRAND.info})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 8px 32px ${BRAND.accent}44`,
          }}>
            <Icon name="sparkle" size={36} color="#fff" />
          </div>
          <h1 style={{ color: BRAND.text, fontSize: 26, fontWeight: 800, margin: 0, letterSpacing: "-0.5px", fontFamily: "'DM Sans', sans-serif" }}>
            Mezzofy AI
          </h1>
          <p style={{ color: BRAND.textMuted, fontSize: 14, margin: "8px 0 0", fontWeight: 400 }}>
            Your intelligent work assistant
          </p>
        </div>

        {/* Inputs */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ position: "relative" }}>
            <div style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)" }}>
              <Icon name="user" size={18} color={BRAND.textDim} />
            </div>
            <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" style={{
              width: "100%", padding: "16px 16px 16px 48px", borderRadius: 14,
              background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
              color: BRAND.text, fontSize: 15, outline: "none", boxSizing: "border-box",
              fontFamily: "'DM Sans', sans-serif",
            }} />
          </div>
          <div style={{ position: "relative" }}>
            <div style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)" }}>
              <Icon name="lock" size={18} color={BRAND.textDim} />
            </div>
            <input value={pass} type="password" onChange={e => setPass(e.target.value)} placeholder="Password" style={{
              width: "100%", padding: "16px 16px 16px 48px", borderRadius: 14,
              background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
              color: BRAND.text, fontSize: 15, outline: "none", boxSizing: "border-box",
              fontFamily: "'DM Sans', sans-serif",
            }} />
          </div>
        </div>

        {/* Login Button */}
        <button onClick={handleLogin} disabled={loading} style={{
          marginTop: 24, padding: "16px", borderRadius: 14, border: "none",
          background: loading ? BRAND.textDim : `linear-gradient(135deg, ${BRAND.accent}, #00B890)`,
          color: "#fff", fontSize: 16, fontWeight: 700, cursor: "pointer",
          boxShadow: loading ? "none" : `0 4px 20px ${BRAND.accent}44`,
          transition: "all 0.3s", fontFamily: "'DM Sans', sans-serif",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
        }}>
          {loading ? (
            <div style={{
              width: 20, height: 20, border: "2px solid rgba(255,255,255,0.3)",
              borderTopColor: "#fff", borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }} />
          ) : "Sign In"}
        </button>

        <p style={{ textAlign: "center", color: BRAND.textDim, fontSize: 13, marginTop: 20 }}>
          Forgot password? <span style={{ color: BRAND.accent, cursor: "pointer" }}>Reset here</span>
        </p>
      </div>

      {/* Bottom safe area */}
      <div style={{ height: 34 }} />

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </PhoneFrame>
  );
};

// ════════════════════════════════════════
// ═══ CHAT SCREEN
// ════════════════════════════════════════
const ChatScreen = ({ user, onNav }) => {
  const [messages, setMessages] = useState([
    { id: 1, role: "assistant", text: `Good morning, ${user.name.split(" ")[0]}! How can I help the ${user.department} team today?`, time: "9:41 AM" },
  ]);
  const [input, setInput] = useState("");
  const [inputMode, setInputMode] = useState("text");
  const [isTyping, setIsTyping] = useState(false);
  const [showModes, setShowModes] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordTime, setRecordTime] = useState(0);
  const [mediaPreview, setMediaPreview] = useState(null);
  const messagesEnd = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  useEffect(() => {
    if (recording) {
      timerRef.current = setInterval(() => setRecordTime(t => t + 1), 1000);
    } else {
      clearInterval(timerRef.current);
      setRecordTime(0);
    }
    return () => clearInterval(timerRef.current);
  }, [recording]);

  const demoResponses = {
    finance: {
      text: "I've generated the Q4 2025 Financial Statement. Revenue is up 23% YoY at $1.8M. The PDF has been emailed to CEO James Wong.",
      artifacts: [{ type: "pdf", name: "Financial_Statement_Q4_2025.pdf", size: "2.4 MB" }],
      tools: ["database_query", "pdf_generator", "email_send"],
    },
    sales: {
      text: "Found 23 F&B companies in Singapore. I've saved them to CRM and sent personalized intro emails to 20 contacts with valid emails.",
      artifacts: [{ type: "csv", name: "leads_singapore_fnb.csv", size: "48 KB" }],
      tools: ["linkedin_search", "crm_save", "email_batch_send"],
    },
    marketing: {
      text: "Here's the website copy and customer playbook for the new Loyalty 2.0 feature. Both use our latest brand guidelines and product specs.",
      artifacts: [
        { type: "md", name: "loyalty_website_copy.md", size: "12 KB" },
        { type: "pdf", name: "Loyalty_2.0_Playbook.pdf", size: "3.1 MB" },
      ],
      tools: ["knowledge_search", "content_generator", "pdf_generator"],
    },
    support: {
      text: "This week: 47 tickets, 89% resolved within SLA. Recurring issue: 12 tickets about coupon redemption timeout. Recommend engineering review.",
      artifacts: [{ type: "pdf", name: "Support_Weekly_Report.pdf", size: "1.8 MB" }],
      tools: ["database_query", "data_analysis", "pdf_generator"],
    },
    management: {
      text: "Cross-department KPI report is ready. Highlights: Sales pipeline at $420K (+18%), support SLA at 89%, marketing shipped 3 campaigns. LLM costs: $127 this month.",
      artifacts: [{ type: "pdf", name: "KPI_Dashboard_Feb_2026.pdf", size: "2.7 MB" }],
      tools: ["query_all_departments", "data_analysis", "pdf_generator"],
    },
  };

  const sendMessage = (text, type = "text", mediaInfo = null) => {
    if (!text && !mediaInfo) return;
    const newMsg = {
      id: Date.now(), role: "user", text: text || "",
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      type, media: mediaInfo,
    };
    setMessages(prev => [...prev, newMsg]);
    setInput("");
    setMediaPreview(null);
    setIsTyping(true);

    setTimeout(() => {
      const resp = demoResponses[user.department] || demoResponses.sales;
      setMessages(prev => [...prev, {
        id: Date.now() + 1, role: "assistant", text: resp.text,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        artifacts: resp.artifacts, tools: resp.tools,
      }]);
      setIsTyping(false);
    }, 2200);
  };

  const handleModeAction = (mode) => {
    setInputMode(mode);
    setShowModes(false);
    if (mode === "image") {
      setMediaPreview({ type: "image", name: "receipt_photo.jpg", size: "1.2 MB", emoji: "📷" });
    } else if (mode === "video") {
      setMediaPreview({ type: "video", name: "product_demo.mp4", size: "24 MB", emoji: "🎥" });
    } else if (mode === "file") {
      setMediaPreview({ type: "file", name: "Q4_Report.pdf", size: "2.1 MB", emoji: "📎" });
    } else if (mode === "url") {
      setInput("https://");
    } else if (mode === "audio") {
      setMediaPreview({ type: "audio", name: "voice_memo.m4a", size: "340 KB", emoji: "🔊" });
    }
  };

  const inputModes = [
    { id: "text", icon: "chat", label: "Text", color: BRAND.accent },
    { id: "image", icon: "image", label: "Image", color: "#4DA6FF" },
    { id: "video", icon: "video", label: "Video", color: "#C77DFF" },
    { id: "camera", icon: "camera", label: "Camera", color: "#FF6B8A" },
    { id: "speech", icon: "mic", label: "Speech", color: "#00D4AA" },
    { id: "audio", icon: "audio", label: "Audio", color: "#FFB84D" },
    { id: "file", icon: "file", label: "File", color: "#4DA6FF" },
    { id: "url", icon: "globe", label: "URL", color: "#FF6B8A" },
  ];

  const formatSecs = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <>
      {/* Header */}
      <div style={{
        padding: "8px 20px 12px", display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: `1px solid ${BRAND.border}`,
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 style={{ color: BRAND.text, fontSize: 20, fontWeight: 800, margin: 0, fontFamily: "'DM Sans', sans-serif" }}>Mezzofy AI</h2>
            <DeptBadge dept={user.department} compact />
          </div>
          <p style={{ color: BRAND.textMuted, fontSize: 12, margin: "2px 0 0" }}>
            {user.name} · {user.role.replace("_", " ")}
          </p>
        </div>
        <button onClick={() => onNav("history")} style={{ background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`, borderRadius: 12, padding: 10, cursor: "pointer" }}>
          <Icon name="plus" size={18} color={BRAND.accent} />
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 16px 8px" }}>
        {messages.map(msg => (
          <div key={msg.id} style={{
            display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            marginBottom: 16,
          }}>
            <div style={{ maxWidth: "82%" }}>
              {/* Media indicator */}
              {msg.media && (
                <div style={{
                  background: msg.role === "user" ? BRAND.accent + "22" : BRAND.surfaceLight,
                  borderRadius: "14px 14px 0 0", padding: "10px 14px",
                  border: `1px solid ${msg.role === "user" ? BRAND.accent + "33" : BRAND.border}`,
                  borderBottom: "none", display: "flex", alignItems: "center", gap: 8,
                  fontSize: 13, color: BRAND.textMuted,
                }}>
                  <span style={{ fontSize: 18 }}>{msg.media.emoji}</span>
                  <span style={{ fontWeight: 600, color: BRAND.text }}>{msg.media.name}</span>
                  <span style={{ opacity: 0.6 }}>{msg.media.size}</span>
                </div>
              )}
              {/* Bubble */}
              <div style={{
                background: msg.role === "user"
                  ? `linear-gradient(135deg, ${BRAND.accent}, #00B890)`
                  : BRAND.surfaceLight,
                padding: "12px 16px",
                borderRadius: msg.media
                  ? (msg.role === "user" ? "0 0 4px 14px" : "0 0 14px 4px")
                  : (msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px"),
                color: msg.role === "user" ? "#fff" : BRAND.text,
                fontSize: 14, lineHeight: 1.55, fontFamily: "'DM Sans', sans-serif",
                border: msg.role === "user" ? "none" : `1px solid ${BRAND.border}`,
              }}>
                {msg.text}
              </div>
              {/* Artifacts */}
              {msg.artifacts && (
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                  {msg.artifacts.map((a, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 10,
                      background: BRAND.card, border: `1px solid ${BRAND.border}`,
                      borderRadius: 12, padding: "10px 14px", cursor: "pointer",
                    }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: 10,
                        background: a.type === "pdf" ? "#FF4B6E22" : a.type === "csv" ? "#00D4AA22" : "#4DA6FF22",
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <Icon name={a.type === "pdf" ? "pdf" : a.type === "csv" ? "file" : "file"} size={18}
                          color={a.type === "pdf" ? "#FF4B6E" : a.type === "csv" ? "#00D4AA" : "#4DA6FF"} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ color: BRAND.text, fontSize: 13, fontWeight: 600 }}>{a.name}</div>
                        <div style={{ color: BRAND.textMuted, fontSize: 11 }}>{a.size}</div>
                      </div>
                      <Icon name="download" size={16} color={BRAND.accent} />
                    </div>
                  ))}
                </div>
              )}
              {/* Tools used */}
              {msg.tools && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
                  {msg.tools.map((t, i) => (
                    <span key={i} style={{
                      fontSize: 10, padding: "2px 8px", borderRadius: 6,
                      background: BRAND.accent + "12", color: BRAND.accent, fontWeight: 600,
                      border: `1px solid ${BRAND.accent}22`,
                    }}>{t}</span>
                  ))}
                </div>
              )}
              <div style={{ fontSize: 10, color: BRAND.textDim, marginTop: 4, textAlign: msg.role === "user" ? "right" : "left" }}>
                {msg.time}
              </div>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <div style={{ display: "flex", marginBottom: 16 }}>
            <div style={{
              background: BRAND.surfaceLight, borderRadius: "18px 18px 18px 4px",
              padding: "14px 20px", border: `1px solid ${BRAND.border}`,
              display: "flex", alignItems: "center", gap: 6,
            }}>
              <div style={{ display: "flex", gap: 4 }}>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{
                    width: 7, height: 7, borderRadius: "50%", background: BRAND.accent,
                    animation: `bounce 1.4s ease-in-out ${i * 0.2}s infinite`,
                  }} />
                ))}
              </div>
              <span style={{ fontSize: 12, color: BRAND.textMuted, marginLeft: 6 }}>Thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEnd} />
      </div>

      {/* Media Preview */}
      {mediaPreview && (
        <div style={{
          margin: "0 16px", padding: "10px 14px", borderRadius: 14,
          background: BRAND.card, border: `1px solid ${BRAND.border}`,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <span style={{ fontSize: 22 }}>{mediaPreview.emoji}</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: BRAND.text, fontSize: 13, fontWeight: 600 }}>{mediaPreview.name}</div>
            <div style={{ color: BRAND.textMuted, fontSize: 11 }}>{mediaPreview.size}</div>
          </div>
          <button onClick={() => { setMediaPreview(null); setInputMode("text"); }} style={{
            background: "none", border: "none", color: BRAND.textMuted, cursor: "pointer", fontSize: 18, padding: 4,
          }}>✕</button>
        </div>
      )}

      {/* Input Mode Selector */}
      {showModes && (
        <div style={{
          margin: "8px 16px", background: BRAND.card, borderRadius: 16,
          border: `1px solid ${BRAND.border}`, padding: 12,
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8,
        }}>
          {inputModes.map(m => (
            <button key={m.id} onClick={() => handleModeAction(m.id)} style={{
              background: inputMode === m.id ? m.color + "22" : "transparent",
              border: inputMode === m.id ? `1px solid ${m.color}44` : `1px solid transparent`,
              borderRadius: 12, padding: "12px 4px", cursor: "pointer",
              display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
              transition: "all 0.2s",
            }}>
              <Icon name={m.icon} size={20} color={m.color} />
              <span style={{ fontSize: 10, color: BRAND.textMuted, fontWeight: 600 }}>{m.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Speech Recording UI */}
      {recording && (
        <div style={{
          margin: "8px 16px", padding: "20px", borderRadius: 16,
          background: `linear-gradient(135deg, ${BRAND.danger}15, ${BRAND.card})`,
          border: `1px solid ${BRAND.danger}33`,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
        }}>
          <div style={{
            width: 64, height: 64, borderRadius: "50%",
            background: `${BRAND.danger}22`, display: "flex", alignItems: "center", justifyContent: "center",
            animation: "pulse 1.5s ease-in-out infinite",
          }}>
            <Icon name="mic" size={28} color={BRAND.danger} />
          </div>
          <span style={{ color: BRAND.text, fontSize: 22, fontWeight: 700, fontFamily: "'DM Mono', monospace" }}>
            {formatSecs(recordTime)}
          </span>
          <span style={{ color: BRAND.textMuted, fontSize: 12 }}>Listening... Release to send</span>
          <button onClick={() => {
            setRecording(false);
            sendMessage("Generate the latest financial statement and send to CEO", "speech", { type: "speech", name: "Voice message", size: formatSecs(recordTime), emoji: "🎤" });
          }} style={{
            background: BRAND.danger, border: "none", borderRadius: 12, padding: "10px 32px",
            color: "#fff", fontSize: 14, fontWeight: 700, cursor: "pointer",
          }}>
            <Icon name="stop" size={16} color="#fff" /> Stop & Send
          </button>
        </div>
      )}

      {/* Input Bar */}
      {!recording && (
        <div style={{
          padding: "10px 12px 6px", display: "flex", alignItems: "flex-end", gap: 8,
          borderTop: `1px solid ${BRAND.border}`,
        }}>
          <button onClick={() => setShowModes(!showModes)} style={{
            background: showModes ? BRAND.accent + "22" : BRAND.surfaceLight,
            border: `1px solid ${showModes ? BRAND.accent + "44" : BRAND.border}`,
            borderRadius: 12, padding: 10, cursor: "pointer", flexShrink: 0,
          }}>
            <Icon name="plus" size={20} color={showModes ? BRAND.accent : BRAND.textMuted} />
          </button>

          {inputMode === "speech" ? (
            <button
              onMouseDown={() => setRecording(true)}
              style={{
                flex: 1, padding: "14px", borderRadius: 14, border: `2px dashed ${BRAND.accent}44`,
                background: BRAND.accentSoft, color: BRAND.accent, fontSize: 14, fontWeight: 600,
                cursor: "pointer", textAlign: "center", fontFamily: "'DM Sans', sans-serif",
              }}
            >
              🎤 Hold to Speak
            </button>
          ) : (
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendMessage(input, inputMode, mediaPreview)}
              placeholder={
                inputMode === "url" ? "Paste URL to analyze..." :
                mediaPreview ? "Add a message (optional)..." :
                "Message Mezzofy AI..."
              }
              style={{
                flex: 1, padding: "14px 16px", borderRadius: 14,
                background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
                color: BRAND.text, fontSize: 14, outline: "none",
                fontFamily: "'DM Sans', sans-serif",
              }}
            />
          )}

          <button onClick={() => sendMessage(input, inputMode, mediaPreview)} style={{
            background: `linear-gradient(135deg, ${BRAND.accent}, #00B890)`,
            border: "none", borderRadius: 12, padding: 12, cursor: "pointer", flexShrink: 0,
            boxShadow: `0 2px 12px ${BRAND.accent}44`,
          }}>
            <Icon name="send" size={18} color="#fff" />
          </button>
        </div>
      )}

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0) }
          40% { transform: translateY(-6px) }
        }
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 ${BRAND.danger}44 }
          50% { box-shadow: 0 0 0 16px ${BRAND.danger}00 }
        }
      `}</style>
    </>
  );
};

// ════════════════════════════════════════
// ═══ CHAT HISTORY SCREEN
// ════════════════════════════════════════
const HistoryScreen = ({ user }) => {
  const sessions = [
    { id: 1, title: "Q4 Financial Statement", dept: "finance", time: "Today, 9:41 AM", preview: "Generated and sent to CEO", tools: 3 },
    { id: 2, title: "Singapore F&B Lead Search", dept: "sales", time: "Yesterday, 3:22 PM", preview: "23 leads found, 20 emails sent", tools: 4 },
    { id: 3, title: "Loyalty 2.0 Playbook", dept: "marketing", time: "Feb 24, 11:05 AM", preview: "Website copy + playbook PDF created", tools: 3 },
    { id: 4, title: "Pitch Deck — ABC Restaurant", dept: "sales", time: "Feb 23, 2:15 PM", preview: "10-slide PPTX generated", tools: 5 },
    { id: 5, title: "Weekly Support Summary", dept: "support", time: "Feb 22, 9:00 AM", preview: "47 tickets analyzed, 3 recurring issues", tools: 3 },
    { id: 6, title: "Monthly KPI Dashboard", dept: "management", time: "Feb 20, 10:30 AM", preview: "Cross-department report generated", tools: 6 },
  ];

  return (
    <>
      <div style={{ padding: "8px 20px 12px" }}>
        <h2 style={{ color: BRAND.text, fontSize: 20, fontWeight: 800, margin: 0, fontFamily: "'DM Sans', sans-serif" }}>Chat History</h2>
        <p style={{ color: BRAND.textMuted, fontSize: 12, margin: "2px 0 0" }}>{sessions.length} conversations</p>
      </div>
      {/* Search */}
      <div style={{ padding: "0 16px 12px" }}>
        <div style={{ position: "relative" }}>
          <div style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }}>
            <Icon name="search" size={16} color={BRAND.textDim} />
          </div>
          <input placeholder="Search conversations..." style={{
            width: "100%", padding: "12px 12px 12px 42px", borderRadius: 12,
            background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
            color: BRAND.text, fontSize: 14, outline: "none", boxSizing: "border-box",
            fontFamily: "'DM Sans', sans-serif",
          }} />
        </div>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "0 16px" }}>
        {sessions.map(s => (
          <div key={s.id} style={{
            padding: "14px 16px", borderRadius: 14, marginBottom: 8,
            background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
            cursor: "pointer", transition: "all 0.2s",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ color: BRAND.text, fontSize: 14, fontWeight: 700 }}>{s.title}</span>
                </div>
                <DeptBadge dept={s.dept} compact />
              </div>
              <Icon name="chevron" size={16} color={BRAND.textDim} />
            </div>
            <p style={{ color: BRAND.textMuted, fontSize: 13, margin: "8px 0 0", lineHeight: 1.4 }}>{s.preview}</p>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
              <span style={{ fontSize: 11, color: BRAND.textDim }}>{s.time}</span>
              <span style={{ fontSize: 11, color: BRAND.accent }}>{s.tools} tools used</span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
};

// ════════════════════════════════════════
// ═══ FILES SCREEN
// ════════════════════════════════════════
const FilesScreen = ({ user }) => {
  const files = [
    { id: 1, name: "Financial_Statement_Q4_2025.pdf", type: "pdf", size: "2.4 MB", date: "Today, 9:45 AM", agent: "finance" },
    { id: 2, name: "leads_singapore_fnb.csv", type: "csv", size: "48 KB", date: "Yesterday", agent: "sales" },
    { id: 3, name: "Loyalty_2.0_Playbook.pdf", type: "pdf", size: "3.1 MB", date: "Feb 24", agent: "marketing" },
    { id: 4, name: "Pitch_ABC_Restaurant.pptx", type: "pptx", size: "5.6 MB", date: "Feb 23", agent: "sales" },
    { id: 5, name: "Support_Weekly_Report.pdf", type: "pdf", size: "1.8 MB", date: "Feb 22", agent: "support" },
    { id: 6, name: "KPI_Dashboard_Feb_2026.pdf", type: "pdf", size: "2.7 MB", date: "Feb 20", agent: "management" },
    { id: 7, name: "loyalty_website_copy.md", type: "md", size: "12 KB", date: "Feb 24", agent: "marketing" },
  ];

  const typeStyles = {
    pdf: { bg: "#FF4B6E18", color: "#FF4B6E", label: "PDF" },
    csv: { bg: "#00D4AA18", color: "#00D4AA", label: "CSV" },
    pptx: { bg: "#C77DFF18", color: "#C77DFF", label: "PPTX" },
    md: { bg: "#4DA6FF18", color: "#4DA6FF", label: "MD" },
  };

  return (
    <>
      <div style={{ padding: "8px 20px 12px" }}>
        <h2 style={{ color: BRAND.text, fontSize: 20, fontWeight: 800, margin: 0, fontFamily: "'DM Sans', sans-serif" }}>Generated Files</h2>
        <p style={{ color: BRAND.textMuted, fontSize: 12, margin: "2px 0 0" }}>{files.length} files</p>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "0 16px" }}>
        {files.map(f => {
          const ts = typeStyles[f.type] || typeStyles.md;
          return (
            <div key={f.id} style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "14px 16px", borderRadius: 14, marginBottom: 8,
              background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
              cursor: "pointer",
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12, background: ts.bg,
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0,
              }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: ts.color }}>{ts.label}</span>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  color: BRAND.text, fontSize: 13, fontWeight: 600,
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}>{f.name}</div>
                <div style={{ display: "flex", gap: 8, marginTop: 3 }}>
                  <span style={{ fontSize: 11, color: BRAND.textMuted }}>{f.size}</span>
                  <span style={{ fontSize: 11, color: BRAND.textDim }}>·</span>
                  <span style={{ fontSize: 11, color: BRAND.textMuted }}>{f.date}</span>
                </div>
              </div>
              <DeptBadge dept={f.agent} compact />
              <Icon name="download" size={18} color={BRAND.accent} />
            </div>
          );
        })}
      </div>
    </>
  );
};

// ════════════════════════════════════════
// ═══ SETTINGS SCREEN
// ════════════════════════════════════════
const SettingsScreen = ({ user, onLogout }) => {
  const SettingsRow = ({ icon, label, value, accent, danger, onClick }) => (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 14, width: "100%",
      padding: "14px 16px", background: "none", border: "none", cursor: "pointer",
      borderBottom: `1px solid ${BRAND.border}08`,
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 10,
        background: danger ? "#FF4B6E14" : accent ? BRAND.accentSoft : BRAND.surfaceLight,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Icon name={icon} size={18} color={danger ? BRAND.danger : accent ? BRAND.accent : BRAND.textMuted} />
      </div>
      <div style={{ flex: 1, textAlign: "left" }}>
        <span style={{ fontSize: 14, color: danger ? BRAND.danger : BRAND.text, fontWeight: 500 }}>{label}</span>
      </div>
      {value && <span style={{ fontSize: 13, color: BRAND.textMuted }}>{value}</span>}
      <Icon name="chevron" size={16} color={BRAND.textDim} />
    </button>
  );

  return (
    <>
      <div style={{ padding: "8px 20px 12px" }}>
        <h2 style={{ color: BRAND.text, fontSize: 20, fontWeight: 800, margin: 0, fontFamily: "'DM Sans', sans-serif" }}>Settings</h2>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "0 16px" }}>
        {/* Profile Card */}
        <div style={{
          padding: "20px", borderRadius: 16, marginBottom: 16,
          background: `linear-gradient(135deg, ${BRAND.surfaceLight}, ${BRAND.card})`,
          border: `1px solid ${BRAND.border}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16,
              background: `linear-gradient(135deg, ${BRAND.accent}, ${BRAND.info})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 22, fontWeight: 800, color: "#fff", fontFamily: "'DM Sans', sans-serif",
            }}>
              {user.name.split(" ").map(n => n[0]).join("")}
            </div>
            <div>
              <div style={{ color: BRAND.text, fontSize: 17, fontWeight: 700 }}>{user.name}</div>
              <div style={{ color: BRAND.textMuted, fontSize: 13, margin: "2px 0 6px" }}>{user.email}</div>
              <DeptBadge dept={user.department} />
            </div>
          </div>
        </div>

        {/* Settings Groups */}
        <div style={{
          borderRadius: 14, overflow: "hidden", marginBottom: 12,
          background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
        }}>
          <SettingsRow icon="user" label="Edit Profile" />
          <SettingsRow icon="bell" label="Notifications" value="On" />
          <SettingsRow icon="mic" label="Speech Language" value="English" />
          <SettingsRow icon="eye" label="Appearance" value="Dark" />
        </div>

        <div style={{
          borderRadius: 14, overflow: "hidden", marginBottom: 12,
          background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
        }}>
          <SettingsRow icon="shield" label="Privacy & Security" accent />
          <SettingsRow icon="file" label="Storage & Data" value="142 MB" />
          <SettingsRow icon="clock" label="AI Usage Stats" accent />
        </div>

        <div style={{
          borderRadius: 14, overflow: "hidden", marginBottom: 24,
          background: BRAND.surfaceLight, border: `1px solid ${BRAND.border}`,
        }}>
          <SettingsRow icon="logout" label="Sign Out" danger onClick={onLogout} />
        </div>

        <p style={{ textAlign: "center", color: BRAND.textDim, fontSize: 11, marginBottom: 20 }}>
          Mezzofy AI Assistant v1.0.0
        </p>
      </div>
    </>
  );
};

// ════════════════════════════════════════
// ═══ CAMERA SCREEN
// ════════════════════════════════════════
const CameraScreen = ({ onBack }) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);

  const handleCapture = () => {
    setAnalyzing(true);
    setTimeout(() => {
      setAnalyzing(false);
      setResult("Business card detected: John Tan, CEO at ABC Restaurant Group. Email: john@abcrestaurant.sg, Phone: +65 9123 4567. Shall I save this as a sales lead?");
    }, 2000);
  };

  return (
    <>
      <div style={{ padding: "8px 20px 12px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}>
          <Icon name="back" size={22} color={BRAND.text} />
        </button>
        <h2 style={{ color: BRAND.text, fontSize: 18, fontWeight: 700, margin: 0, fontFamily: "'DM Sans', sans-serif" }}>Live Camera</h2>
        <div style={{
          marginLeft: "auto", width: 8, height: 8, borderRadius: "50%",
          background: BRAND.danger, boxShadow: `0 0 8px ${BRAND.danger}`,
          animation: "pulse 1.5s ease-in-out infinite",
        }} />
      </div>

      {/* Camera Viewfinder */}
      <div style={{
        flex: 1, margin: "0 16px", borderRadius: 20, overflow: "hidden",
        background: "#0a0e14",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        position: "relative",
        border: `2px solid ${analyzing ? BRAND.accent : BRAND.border}`,
        transition: "border-color 0.3s",
      }}>
        {/* Simulated camera view */}
        <div style={{
          width: "80%", height: "50%", borderRadius: 12, position: "relative",
          background: `linear-gradient(145deg, #1a1e28, #0d1117)`,
          border: `1px dashed ${BRAND.textDim}`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{ textAlign: "center" }}>
            <Icon name="camera" size={48} color={BRAND.textDim} />
            <p style={{ color: BRAND.textDim, fontSize: 13, marginTop: 12 }}>Point camera at object</p>
          </div>
          {/* Corner markers */}
          {[{ top: -2, left: -2 }, { top: -2, right: -2 }, { bottom: -2, left: -2 }, { bottom: -2, right: -2 }].map((pos, i) => (
            <div key={i} style={{
              position: "absolute", ...pos, width: 24, height: 24,
              borderTop: i < 2 ? `3px solid ${BRAND.accent}` : "none",
              borderBottom: i >= 2 ? `3px solid ${BRAND.accent}` : "none",
              borderLeft: i % 2 === 0 ? `3px solid ${BRAND.accent}` : "none",
              borderRight: i % 2 === 1 ? `3px solid ${BRAND.accent}` : "none",
              borderRadius: 4,
            }} />
          ))}
        </div>

        {analyzing && (
          <div style={{
            position: "absolute", bottom: 20, left: 20, right: 20,
            background: BRAND.primary + "ee", borderRadius: 12, padding: "12px 16px",
            border: `1px solid ${BRAND.accent}44`,
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <div style={{
              width: 20, height: 20, border: `2px solid ${BRAND.accent}44`,
              borderTopColor: BRAND.accent, borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }} />
            <span style={{ color: BRAND.accent, fontSize: 13, fontWeight: 600 }}>Analyzing frame...</span>
          </div>
        )}

        {result && (
          <div style={{
            position: "absolute", bottom: 20, left: 20, right: 20,
            background: BRAND.primary + "f0", borderRadius: 14, padding: "14px 16px",
            border: `1px solid ${BRAND.accent}44`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <Icon name="check" size={16} color={BRAND.accent} />
              <span style={{ color: BRAND.accent, fontSize: 12, fontWeight: 700 }}>AI Analysis</span>
            </div>
            <p style={{ color: BRAND.text, fontSize: 13, lineHeight: 1.5, margin: 0 }}>{result}</p>
          </div>
        )}
      </div>

      {/* Capture Button */}
      <div style={{ padding: "20px 0 40px", display: "flex", justifyContent: "center" }}>
        <button onClick={handleCapture} style={{
          width: 72, height: 72, borderRadius: "50%", cursor: "pointer",
          background: "transparent", border: `4px solid ${BRAND.accent}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: `0 0 24px ${BRAND.accent}33`,
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: "50%",
            background: BRAND.accent, transition: "transform 0.15s",
          }} />
        </button>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </>
  );
};

// ════════════════════════════════════════
// ═══ MAIN APP
// ════════════════════════════════════════
export default function MezzofyAIApp() {
  const [screen, setScreen] = useState("login");
  const [activeTab, setActiveTab] = useState("chat");

  const user = {
    name: "Sarah Chen",
    email: "sarah@mezzofy.com",
    department: "sales",
    role: "sales_rep",
    permissions: ["sales_read", "sales_write", "email_send", "linkedin_access"],
  };

  const handleLogin = () => setScreen("app");
  const handleLogout = () => { setScreen("login"); setActiveTab("chat"); };

  const handleNav = (tab) => {
    if (tab === "camera") {
      setScreen("camera");
    } else {
      setActiveTab(tab);
      setScreen("app");
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(160deg, #060B14, #0A1628, #0D1B30)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "40px 20px",
      fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet" />

      {screen === "login" && <LoginScreen onLogin={handleLogin} />}

      {screen === "app" && (
        <PhoneFrame>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {activeTab === "chat" && <ChatScreen user={user} onNav={handleNav} />}
            {activeTab === "history" && <HistoryScreen user={user} />}
            {activeTab === "files" && <FilesScreen user={user} />}
            {activeTab === "settings" && <SettingsScreen user={user} onLogout={handleLogout} />}
          </div>
          <TabBar active={activeTab} onNav={handleNav} />
        </PhoneFrame>
      )}

      {screen === "camera" && (
        <PhoneFrame>
          <CameraScreen onBack={() => setScreen("app")} />
        </PhoneFrame>
      )}
    </div>
  );
}
