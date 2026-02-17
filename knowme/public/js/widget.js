(function () {
  "use strict";

  // ── Config from script tag (defaults) ──────────────────────────
  const scriptTag = document.currentScript;
  const CONFIG = {
    token: scriptTag?.getAttribute("data-token") || "",
    host: (scriptTag?.getAttribute("data-host") || "").replace(/\/$/, ""),
    accent: scriptTag?.getAttribute("data-accent") || "#FF6B6B",
    botName: "Know Me",
    greetingMessage: "",
    initialChips: [],
    maxMessages: 18,
  };

  const API_URL = CONFIG.host + "/api/method/knowme.api.chat.handle";
  const CONFIG_URL = CONFIG.host + "/api/method/knowme.api.config.get_widget_config";

  // ── Session State ───────────────────────────────────────────────
  const state = {
    open: false,
    loading: false,
    sessionId: "km_" + Math.random().toString(36).slice(2, 11),
    messages: [],
    conversationHistory: [],
    messageCount: 0,
    maxMessages: 18,
    chips: [],
    ended: false,
  };

  // ── Fetch tenant config from server ────────────────────────────
  function fetchConfig() {
    return fetch(CONFIG_URL + "?token=" + encodeURIComponent(CONFIG.token), {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Config fetch failed: " + res.status);
        return res.json();
      })
      .then(function (data) {
        var cfg = data.message || data;
        if (cfg.accentColor) CONFIG.accent = cfg.accentColor;
        if (cfg.botName) CONFIG.botName = cfg.botName;
        if (cfg.greetingMessage) CONFIG.greetingMessage = cfg.greetingMessage;
        if (cfg.maxMessages) CONFIG.maxMessages = cfg.maxMessages;
        if (cfg.suggestedChips && cfg.suggestedChips.length > 0) {
          CONFIG.initialChips = cfg.suggestedChips;
        }
        state.maxMessages = CONFIG.maxMessages;
      })
      .catch(function (err) {
        console.warn("KnowMe: could not fetch config, using defaults", err);
      });
  }

  // ── Dark mode detection ─────────────────────────────────────────
  function isDarkMode() {
    return (
      document.documentElement.classList.contains("dark") ||
      document.body.classList.contains("dark-mode") ||
      window.matchMedia("(prefers-color-scheme: dark)").matches
    );
  }

  // ── Color helpers ───────────────────────────────────────────────
  function hexToRgb(hex) {
    var clean = hex.replace("#", "");
    if (clean.length === 3) {
      clean = clean[0]+clean[0]+clean[1]+clean[1]+clean[2]+clean[2];
    }
    var r = parseInt(clean.slice(0, 2), 16);
    var g = parseInt(clean.slice(2, 4), 16);
    var b = parseInt(clean.slice(4, 6), 16);
    return { r: r, g: g, b: b };
  }

  // ── Inject Styles ──────────────────────────────────────────────
  function injectStyles() {
    var accent = CONFIG.accent;
    var rgb = hexToRgb(accent);

    var style = document.createElement("style");
    style.textContent = `
      /* ── KnowMe Widget Styles ── */
      .km-orb {
        position: fixed;
        bottom: 24px;
        right: 24px;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        background: ${accent};
        cursor: pointer;
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 20px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.4);
        transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
        animation: km-pulse 2.5s ease-in-out infinite;
      }
      .km-orb:hover {
        transform: scale(1.1);
        box-shadow: 0 6px 28px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.6);
      }
      .km-orb.km-open {
        animation: none;
        transform: scale(0.9);
      }
      .km-orb svg {
        width: 26px;
        height: 26px;
        fill: white;
        transition: transform 0.3s ease;
      }
      .km-orb.km-open svg {
        transform: rotate(45deg);
      }

      @keyframes km-pulse {
        0%, 100% { box-shadow: 0 4px 20px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.4); }
        50% { box-shadow: 0 4px 32px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.7); }
      }

      /* ── Panel ── */
      .km-panel {
        position: fixed;
        bottom: 92px;
        right: 24px;
        width: 400px;
        height: 560px;
        background: #ffffff;
        border-radius: 16px;
        box-shadow: 0 12px 48px rgba(0,0,0,0.15);
        z-index: 10001;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        transform: scale(0) translateY(20px);
        transform-origin: bottom right;
        opacity: 0;
        transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.25s ease;
        pointer-events: none;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        line-height: 1.5;
        color: #1a1a2e;
      }
      .km-panel.km-visible {
        transform: scale(1) translateY(0);
        opacity: 1;
        pointer-events: all;
      }

      /* ── Dark mode ── */
      .km-panel.km-dark {
        background: #1a1a2e;
        color: #e0e0e0;
        box-shadow: 0 12px 48px rgba(0,0,0,0.4);
      }

      /* ── Header ── */
      .km-header {
        display: flex;
        align-items: center;
        padding: 16px 20px;
        border-bottom: 1px solid #f0f0f0;
        background: ${accent};
        color: white;
        flex-shrink: 0;
      }
      .km-dark .km-header {
        border-bottom-color: #2a2a4a;
      }
      .km-header-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 12px;
        font-size: 18px;
      }
      .km-header-title {
        font-weight: 600;
        font-size: 16px;
        flex: 1;
      }
      .km-header-close {
        width: 32px;
        height: 32px;
        border: none;
        background: rgba(255,255,255,0.15);
        border-radius: 50%;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 18px;
        transition: background 0.2s;
      }
      .km-header-close:hover {
        background: rgba(255,255,255,0.3);
      }

      /* ── Messages ── */
      .km-messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        scroll-behavior: smooth;
      }
      .km-messages::-webkit-scrollbar { width: 4px; }
      .km-messages::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }
      .km-dark .km-messages::-webkit-scrollbar-thumb { background: #444; }

      .km-msg {
        max-width: 85%;
        padding: 10px 14px;
        border-radius: 16px;
        animation: km-fadeIn 0.3s ease;
        word-wrap: break-word;
      }
      .km-msg-ai {
        align-self: flex-start;
        background: #f5f5f5;
        border-bottom-left-radius: 4px;
      }
      .km-dark .km-msg-ai {
        background: #2a2a4a;
      }
      .km-msg-user {
        align-self: flex-end;
        background: ${accent};
        color: white;
        border-bottom-right-radius: 4px;
      }

      @keyframes km-fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }

      /* ── Typing indicator ── */
      .km-typing {
        display: flex;
        gap: 4px;
        padding: 12px 16px;
        align-self: flex-start;
        background: #f5f5f5;
        border-radius: 16px;
        border-bottom-left-radius: 4px;
      }
      .km-dark .km-typing {
        background: #2a2a4a;
      }
      .km-typing-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #999;
        animation: km-bounce 1.4s ease-in-out infinite;
      }
      .km-dark .km-typing-dot { background: #666; }
      .km-typing-dot:nth-child(2) { animation-delay: 0.2s; }
      .km-typing-dot:nth-child(3) { animation-delay: 0.4s; }

      @keyframes km-bounce {
        0%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-6px); }
      }

      /* ── Cards ── */
      .km-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        margin-top: 8px;
        background: #fff;
        border: 1px solid #e8e8e8;
        border-radius: 12px;
        cursor: pointer;
        transition: border-color 0.2s, box-shadow 0.2s;
      }
      .km-card:hover {
        border-color: ${accent};
        box-shadow: 0 2px 12px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.15);
      }
      .km-dark .km-card {
        background: #1e1e3a;
        border-color: #3a3a5a;
      }
      .km-dark .km-card:hover {
        border-color: ${accent};
      }
      .km-card-icon {
        font-size: 24px;
        flex-shrink: 0;
      }
      .km-card-content {
        flex: 1;
        min-width: 0;
      }
      .km-card-title {
        font-weight: 600;
        font-size: 13px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .km-card-type {
        font-size: 11px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .km-card-arrow {
        color: #ccc;
        font-size: 18px;
        flex-shrink: 0;
      }

      /* ── Chips ── */
      .km-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px 16px;
        border-top: 1px solid #f0f0f0;
        flex-shrink: 0;
      }
      .km-dark .km-chips {
        border-top-color: #2a2a4a;
      }
      .km-chip {
        padding: 6px 14px;
        border: 1px solid #e0e0e0;
        border-radius: 20px;
        background: transparent;
        cursor: pointer;
        font-size: 13px;
        color: inherit;
        transition: all 0.2s ease;
        animation: km-chipIn 0.3s ease forwards;
        opacity: 0;
        white-space: nowrap;
      }
      .km-dark .km-chip {
        border-color: #3a3a5a;
      }
      .km-chip:hover {
        background: ${accent};
        color: white;
        border-color: ${accent};
      }

      @keyframes km-chipIn {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
      }

      /* ── Input area ── */
      .km-input-area {
        display: flex;
        gap: 8px;
        padding: 12px 16px;
        border-top: 1px solid #f0f0f0;
        align-items: center;
        flex-shrink: 0;
      }
      .km-dark .km-input-area {
        border-top-color: #2a2a4a;
      }
      .km-input {
        flex: 1;
        padding: 10px 16px;
        border: 1px solid #e0e0e0;
        border-radius: 24px;
        outline: none;
        font-size: 14px;
        font-family: inherit;
        background: transparent;
        color: inherit;
        transition: border-color 0.2s;
      }
      .km-dark .km-input {
        border-color: #3a3a5a;
      }
      .km-input:focus {
        border-color: ${accent};
      }
      .km-input::placeholder {
        color: #999;
      }
      .km-send-btn {
        width: 40px;
        height: 40px;
        border: none;
        background: ${accent};
        border-radius: 50%;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 18px;
        transition: opacity 0.2s, transform 0.2s;
        flex-shrink: 0;
      }
      .km-send-btn:hover {
        transform: scale(1.05);
      }
      .km-send-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
      }

      /* ── Footer ── */
      .km-footer {
        padding: 8px 16px;
        text-align: center;
        font-size: 11px;
        color: #999;
        border-top: 1px solid #f0f0f0;
        flex-shrink: 0;
      }
      .km-dark .km-footer {
        border-top-color: #2a2a4a;
        color: #666;
      }

      /* ── Mobile ── */
      @media (max-width: 640px) {
        .km-panel {
          bottom: 0;
          right: 0;
          width: 100vw;
          height: 100vh;
          height: 100dvh;
          border-radius: 0;
        }
        .km-orb {
          bottom: 16px;
          right: 16px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  // ── Create DOM ─────────────────────────────────────────────────
  function createWidget() {
    // Orb
    var orb = document.createElement("div");
    orb.className = "km-orb";
    orb.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>';
    orb.addEventListener("click", togglePanel);
    document.body.appendChild(orb);

    // Panel
    var panel = document.createElement("div");
    panel.className = "km-panel" + (isDarkMode() ? " km-dark" : "");
    panel.innerHTML =
      '<div class="km-header">' +
        '<div class="km-header-avatar">💬</div>' +
        '<div class="km-header-title">' + escapeHtml(CONFIG.botName) + '</div>' +
        '<button class="km-header-close" aria-label="Close">&times;</button>' +
      '</div>' +
      '<div class="km-messages"></div>' +
      '<div class="km-chips"></div>' +
      '<div class="km-input-area">' +
        '<input class="km-input" type="text" placeholder="Or ask me anything..." maxlength="300" />' +
        '<button class="km-send-btn" aria-label="Send">&#10148;</button>' +
      '</div>' +
      '<div class="km-footer"></div>';
    document.body.appendChild(panel);

    // Event listeners
    panel.querySelector(".km-header-close").addEventListener("click", togglePanel);
    panel.querySelector(".km-send-btn").addEventListener("click", sendUserMessage);
    panel.querySelector(".km-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendUserMessage();
      }
    });

    // Dark mode observer
    var observer = new MutationObserver(function () {
      panel.classList.toggle("km-dark", isDarkMode());
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      panel.classList.toggle("km-dark", isDarkMode());
    });

    return { orb: orb, panel: panel };
  }

  // ── Panel Toggle ───────────────────────────────────────────────
  function togglePanel() {
    state.open = !state.open;
    var orb = document.querySelector(".km-orb");
    var panel = document.querySelector(".km-panel");

    orb.classList.toggle("km-open", state.open);
    panel.classList.toggle("km-visible", state.open);

    if (state.open && state.messages.length === 0) {
      showGreeting();
    }
  }

  // ── Greeting ───────────────────────────────────────────────────
  function showGreeting() {
    // Use server-provided greeting and chips, or fall back to defaults
    var greetingText = CONFIG.greetingMessage ||
      "Hey there! 👋 I'm an AI that knows all about the person behind this site. What would you like to know?";

    var defaultChips = [
      { id: "about", text: "Who are you?", icon: "👤" },
      { id: "skills", text: "What are your skills?", icon: "🛠️" },
      { id: "blog", text: "Show me your writing", icon: "✍️" },
      { id: "interests", text: "What are your interests?", icon: "🎯" },
    ];

    var chips = (CONFIG.initialChips && CONFIG.initialChips.length > 0)
      ? CONFIG.initialChips
      : defaultChips;

    addAIMessage(greetingText);
    renderChips(chips);
    updateFooter();
  }

  // ── Add Messages ───────────────────────────────────────────────
  function addUserMessage(text) {
    state.messages.push({ role: "user", content: text });
    state.conversationHistory.push({ role: "user", content: text });

    var container = document.querySelector(".km-messages");
    var msg = document.createElement("div");
    msg.className = "km-msg km-msg-user";
    msg.textContent = text;
    container.appendChild(msg);
    scrollToBottom();
  }

  function addAIMessage(text, cards) {
    state.messages.push({ role: "ai", content: text });
    state.conversationHistory.push({ role: "assistant", content: text });

    var container = document.querySelector(".km-messages");
    var msg = document.createElement("div");
    msg.className = "km-msg km-msg-ai";
    container.appendChild(msg);

    // Typewriter effect
    typewriter(msg, text, function () {
      if (cards && cards.length > 0) {
        renderCards(msg, cards);
      }
      scrollToBottom();
    });
  }

  // ── Typewriter ─────────────────────────────────────────────────
  function typewriter(el, html, onDone) {
    var i = 0;
    var output = "";
    var inTag = false;

    function tick() {
      if (i >= html.length) {
        el.innerHTML = html;
        if (onDone) onDone();
        return;
      }

      var ch = html[i];
      if (ch === "<") inTag = true;
      if (inTag) {
        // Process entire tag at once
        var tagEnd = html.indexOf(">", i);
        if (tagEnd !== -1) {
          output += html.slice(i, tagEnd + 1);
          i = tagEnd + 1;
          inTag = false;
        } else {
          output += ch;
          i++;
        }
      } else {
        output += ch;
        i++;
      }

      el.innerHTML = output;
      scrollToBottom();
      setTimeout(tick, 18);
    }

    tick();
  }

  // ── Cards ──────────────────────────────────────────────────────
  function renderCards(parentEl, cards) {
    cards.forEach(function (card) {
      var cardEl = document.createElement("div");
      cardEl.className = "km-card";

      var icon = card.type === "blog_post" ? "📝" : "📌";
      cardEl.innerHTML =
        '<div class="km-card-icon">' + icon + '</div>' +
        '<div class="km-card-content">' +
          '<div class="km-card-title">' + escapeHtml(card.title || "") + '</div>' +
          '<div class="km-card-type">' + escapeHtml(card.type || "content") + '</div>' +
        '</div>' +
        '<div class="km-card-arrow">›</div>';

      if (card.slug) {
        cardEl.addEventListener("click", function () {
          window.open("/blog/" + card.slug, "_blank");
        });
      }

      parentEl.appendChild(cardEl);
    });
  }

  // ── Chips ──────────────────────────────────────────────────────
  function renderChips(chips) {
    var container = document.querySelector(".km-chips");
    container.innerHTML = "";
    state.chips = chips || [];

    chips.forEach(function (chip, idx) {
      var btn = document.createElement("button");
      btn.className = "km-chip";
      btn.style.animationDelay = (idx * 0.1) + "s";
      btn.textContent = (chip.icon || "") + " " + chip.text;
      btn.addEventListener("click", function () {
        handleChipClick(chip);
      });
      container.appendChild(btn);
    });
  }

  function handleChipClick(chip) {
    if (state.loading || state.ended) return;
    sendMessage(chip.text);
  }

  // ── Send Message ───────────────────────────────────────────────
  function sendUserMessage() {
    var input = document.querySelector(".km-input");
    var text = input.value.trim();
    if (!text || state.loading || state.ended) return;
    input.value = "";
    sendMessage(text);
  }

  function sendMessage(text) {
    addUserMessage(text);
    state.messageCount++;
    renderChips([]);
    showTyping();
    updateFooter();

    fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-KnowMe-Token": CONFIG.token,
      },
      body: JSON.stringify({
        message: text,
        sessionId: state.sessionId,
        conversationHistory: state.conversationHistory.slice(-12),
        messageCount: state.messageCount,
      }),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        hideTyping();
        var result = data.message || data;

        addAIMessage(result.text || "I'm not sure how to respond to that.", result.cards);
        renderChips(result.chips || []);

        if (result.meta) {
          if (result.meta.remainingMessages !== undefined) {
            state.maxMessages = state.messageCount + result.meta.remainingMessages;
          }
          if (result.meta.isGoodbye) {
            state.ended = true;
            document.querySelector(".km-input").disabled = true;
            document.querySelector(".km-send-btn").disabled = true;
          }
        }

        updateFooter();
      })
      .catch(function (err) {
        hideTyping();
        addAIMessage("I stumbled a bit there. Could you try asking again?");
        renderChips([{ id: "retry", text: "Try again", icon: "🔄" }]);
        console.error("KnowMe widget error:", err);
      });
  }

  // ── Typing Indicator ──────────────────────────────────────────
  function showTyping() {
    state.loading = true;
    var container = document.querySelector(".km-messages");
    var typing = document.createElement("div");
    typing.className = "km-typing";
    typing.id = "km-typing";
    typing.innerHTML =
      '<div class="km-typing-dot"></div>' +
      '<div class="km-typing-dot"></div>' +
      '<div class="km-typing-dot"></div>';
    container.appendChild(typing);
    scrollToBottom();
  }

  function hideTyping() {
    state.loading = false;
    var typing = document.getElementById("km-typing");
    if (typing) typing.remove();
  }

  // ── Footer ─────────────────────────────────────────────────────
  function updateFooter() {
    var footer = document.querySelector(".km-footer");
    if (!footer) return;

    if (state.ended) {
      footer.textContent = "Session ended — refresh to start a new one";
    } else if (state.messageCount > 0) {
      footer.textContent = state.messageCount + "/" + state.maxMessages + " questions";
    } else {
      footer.textContent = "Powered by Know Me";
    }
  }

  // ── Helpers ────────────────────────────────────────────────────
  function scrollToBottom() {
    var container = document.querySelector(".km-messages");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    if (!CONFIG.token || !CONFIG.host) {
      console.warn("KnowMe widget: missing data-token or data-host on script tag");
      return;
    }

    // Fetch config from server, then build widget
    fetchConfig().then(function () {
      injectStyles();
      createWidget();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
