import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import type { ChatMessage, BrowserStatus } from './types';
import { 
  Globe, 
  ExternalLink, 
  Send, 
  Play, 
  RefreshCw, 
  CheckCircle2, 
  ShieldCheck, 
  Bot, 
  User, 
  Lock, 
  FileText 
} from 'lucide-react';

const STARTING_URL = "https://udyamregistration.gov.in/UdyamRegistration.aspx";

export const App: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [wsConnected, setWsConnected] = useState(false);
  const [browserStatus, setBrowserStatus] = useState<BrowserStatus>({
    is_connected: false,
    current_url: STARTING_URL,
    automation_status: 'idle',
    last_inspection_summary: 'Portal session not started yet.',
    detected_step: 'none',
    last_updated: Date.now()
  });

  const wsRef = useRef<WebSocket | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  // Initialize WebSocket connection
  useEffect(() => {
    let reconnectTimeout: any = null;
    let isUnmounted = false;

    const connectWebSocket = () => {
      if (isUnmounted) return;

      // Close previous connection if still open
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        wsRef.current.close();
      }

      const socket = new WebSocket('ws://localhost:8000/ws');
      wsRef.current = socket;

      socket.onopen = () => {
        if (isUnmounted) {
          socket.close();
          return;
        }
        console.log('Connected to backend WebSocket');
        setWsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'init') {
            const data = payload.data;
            if (data.browser_status) setBrowserStatus(data.browser_status);
            if (data.messages && data.messages.length > 0) {
              setMessages((prev) => {
                const existingIds = new Set(prev.map((m) => m.id));
                const newMsgs = data.messages.filter((m: ChatMessage) => !existingIds.has(m.id));
                return [...prev, ...newMsgs];
              });
            }
          } else if (payload.type === 'chat_message') {
            setMessages((prev) => {
              if (prev.some((m) => m.id === payload.data.id)) {
                return prev;
              }
              return [...prev, payload.data];
            });
          } else if (payload.type === 'browser_status') {
            setBrowserStatus(payload.data);
          }
        } catch (e) {
          console.error('Error handling WebSocket message:', e);
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
        if (!isUnmounted) {
          console.log('WebSocket disconnected. Retrying in 2 seconds...');
          reconnectTimeout = setTimeout(connectWebSocket, 2000);
        }
      };

      socket.onerror = (err) => {
        console.error('WebSocket error:', err);
        socket.close();
      };
    };

    connectWebSocket();

    return () => {
      isUnmounted = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendWsAction = (type: string, data: Record<string, any> = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, ...data }));
    }
  };

  const handleSendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim()) return;

    sendWsAction('user_input', { text: inputText.trim() });
    setInputText("");
  };

  const getStatusColorClass = (status: string) => {
    switch (status) {
      case 'verified':
      case 'website_opened':
        return 'status-connected';
      case 'awaiting_user_input':
      case 'awaiting_confirmation':
      case 'awaiting_otp':
      case 'awaiting_captcha':
        return 'status-waiting';
      case 'error':
        return 'status-error';
      default:
        return 'status-active';
    }
  };

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-badge">🇮🇳</div>
          <div>
            <h1 className="brand-title">Udyam AI Login Assistant</h1>
            <p className="brand-subtitle">Playwright MCP • Groq Intelligence • Real-Time Synchronized Browser</p>
          </div>
        </div>

        <div className="header-status-bar">
          {/* Clickable Udyam Portal Hyperlink as required */}
          <div className="url-box">
            <Globe size={16} color="#60a5fa" />
            <a 
              href={browserStatus.current_url || STARTING_URL} 
              target="_blank" 
              rel="noopener noreferrer"
              className="portal-link"
              title="Click to open official Udyam portal in a new browser tab"
            >
              Open Udyam Registration Portal
              <ExternalLink size={14} />
            </a>
          </div>

          <div className={`status-badge ${getStatusColorClass(browserStatus.automation_status)}`}>
            <span className="status-dot"></span>
            Status: {browserStatus.automation_status.replace(/_/g, ' ')}
          </div>

          <div className={`status-badge ${wsConnected ? 'status-connected' : 'status-error'}`}>
            <span className="status-dot"></span>
            {wsConnected ? 'WebSocket Live' : 'Disconnected'}
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="app-content">
        {/* Tab 1: AI Chatbot Interface */}
        <section className="chat-pane">
          <div className="chat-history">
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', margin: 'auto', maxWidth: 460, color: 'var(--text-secondary)' }}>
                <Bot size={48} color="#3b82f6" style={{ margin: '0 auto 16px' }} />
                <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>Ready to Assist with Udyam Portal</h3>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.6, marginBottom: 20 }}>
                  Click <strong>"Start Browser Session"</strong> to launch the visible Playwright browser tab, inspect the actual portal fields with Groq, and begin step-by-step assistance.
                </p>
                <button 
                  className="interactive-action-btn"
                  onClick={() => sendWsAction('start_session')}
                >
                  <Play size={16} /> Start Browser Session
                </button>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`message-row ${msg.sender}`}>
                <div className={`avatar ${msg.sender}`}>
                  {msg.sender === 'bot' ? <Bot size={18} /> : <User size={18} />}
                </div>

                <div className={`bubble ${msg.sender}`}>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>

                  {/* Special Cards */}
                  {msg.message_type === 'link_card' && (
                    <div className="card-link">
                      <a 
                        href={STARTING_URL} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="portal-link"
                        style={{ fontSize: '0.92rem' }}
                      >
                        🔗 Open Udyam Registration Portal (Official) <ExternalLink size={14} />
                      </a>
                    </div>
                  )}

                  {msg.message_type === 'otp_alert' && (
                    <div className="card-alert card-otp">
                      <strong>⚠️ Security Notice:</strong> Please type your Aadhaar OTP directly in the visible browser window. Never share OTPs in chat.
                      <div style={{ marginTop: 8 }}>
                        <button 
                          className="interactive-action-btn"
                          style={{ background: '#d97706' }}
                          onClick={() => sendWsAction('check_otp')}
                        >
                          <CheckCircle2 size={16} /> I have entered & verified OTP
                        </button>
                      </div>
                    </div>
                  )}

                  {msg.message_type === 'captcha_alert' && (
                    <div className="card-alert card-captcha">
                      <strong>⚠️ CAPTCHA Challenge:</strong> Please solve the CAPTCHA image directly in the opened browser window.
                    </div>
                  )}

                  {msg.message_type === 'fill_prompt' && (
                    <div style={{ marginTop: 10 }}>
                      <button 
                        className="interactive-action-btn"
                        onClick={() => sendWsAction('fill_form')}
                      >
                        <FileText size={16} /> Fill Form in Browser
                      </button>
                    </div>
                  )}

                  {msg.message_type === 'otp_prompt' && (
                    <div style={{ marginTop: 10 }}>
                      <button 
                        className="interactive-action-btn"
                        style={{ background: '#059669' }}
                        onClick={() => sendWsAction('trigger_otp')}
                      >
                        <Play size={16} /> Click 'Validate & Generate OTP'
                      </button>
                    </div>
                  )}

                  {msg.message_type === 'otp_validate_prompt' && (
                    <div style={{ marginTop: 10 }}>
                      <button 
                        className="interactive-action-btn"
                        style={{ background: '#059669' }}
                        onClick={() => sendWsAction('validate_otp')}
                      >
                        <CheckCircle2 size={16} /> Submit & Validate OTP on Website
                      </button>
                    </div>
                  )}

                  {msg.message_type === 'success_alert' && (
                    <div className="card-alert card-success">
                      <strong>Access Confirmed:</strong> Authentication stage completed successfully! You can now continue your registration directly in the portal tab.
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={chatBottomRef} />
          </div>

          {/* Quick Actions & Input Bar */}
          <div className="chat-input-container">
            <div className="quick-actions-bar">
              <button 
                className="action-chip primary"
                onClick={() => sendWsAction('start_session')}
                title="Launch visible browser and navigate to Udyam"
              >
                <Play size={14} /> Start / Connect Browser
              </button>
              <button 
                className="action-chip"
                onClick={() => sendWsAction('inspect_page')}
                title="Capture accessibility tree and re-analyze with Groq"
              >
                <RefreshCw size={14} /> Re-inspect Portal
              </button>
              <button 
                className="action-chip"
                onClick={() => sendWsAction('fill_form')}
                title="Fill collected fields into the browser"
              >
                <FileText size={14} /> Fill Form
              </button>
              <button 
                className="action-chip warning"
                onClick={() => sendWsAction('check_otp')}
                title="Check if OTP was verified on the portal"
              >
                <ShieldCheck size={14} /> Check OTP Status
              </button>
            </div>

            <form onSubmit={handleSendMessage} className="input-row">
              <input 
                type="text" 
                className="text-input"
                placeholder="Type your answer or command here (e.g. Aadhaar number, Name, or instructions)..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
              />
              <button type="submit" className="send-btn" disabled={!inputText.trim()}>
                <Send size={16} /> Send
              </button>
            </form>
          </div>
        </section>

        {/* Tab 2/Sidebar: Browser State & Inspection Inspector */}
        <aside className="side-pane">
          <div className="inspector-section">
            <div className="section-header">
              <span>Browser & Portal Status</span>
              <Globe size={16} color="#3b82f6" />
            </div>
            <div className="info-grid">
              <div className="info-item">
                <span className="info-label">Current Browser URL</span>
                <span className="info-val">
                  <a 
                    href={browserStatus.current_url || STARTING_URL} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="portal-link"
                  >
                    Open Udyam Registration Portal ↗
                  </a>
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Full URL Path</span>
                <span className="info-val" style={{ fontSize: '0.78rem' }}>
                  {browserStatus.current_url || STARTING_URL}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Browser Connection</span>
                <span className="info-val">
                  {browserStatus.is_connected ? '🟢 Visible Headed Chromium (Playwright MCP)' : '⚪ Disconnected'}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Detected Stage</span>
                <span className="info-val" style={{ textTransform: 'uppercase' }}>
                  {browserStatus.detected_step}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Current Automation State</span>
                <span className="info-val">
                  {browserStatus.automation_status}
                </span>
              </div>
            </div>
          </div>

          <div className="inspector-section">
            <div className="section-header">
              <span>Last Inspection Result</span>
              <FileText size={16} color="#10b981" />
            </div>
            <p style={{ fontSize: '0.85rem', color: '#e5e7eb', lineHeight: 1.5 }}>
              {browserStatus.last_inspection_summary}
            </p>
          </div>

          <div className="inspector-section">
            <div className="section-header">
              <span>Security & Compliance</span>
              <Lock size={16} color="#f59e0b" />
            </div>
            <ul className="security-checklist">
              <li className="security-item">
                <span className="check-icon">✓</span>
                <span>GROQ_API_KEY protected strictly in backend (.env)</span>
              </li>
              <li className="security-item">
                <span className="check-icon">✓</span>
                <span>OTP entered directly on official website tab</span>
              </li>
              <li className="security-item">
                <span className="check-icon">✓</span>
                <span>Aadhaar numbers masked in logs & chat display</span>
              </li>
              <li className="security-item">
                <span className="check-icon">✓</span>
                <span>Navigation restricted to udyamregistration.gov.in</span>
              </li>
              <li className="security-item">
                <span className="check-icon">✓</span>
                <span>No captcha/authentication bypass attempts</span>
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default App;
