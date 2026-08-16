/**
 * AgentForge Multi-Agent WebUI & GUI Client Controller
 * Multi-Theme Engine (Cheese Theme default), Reactive WebSockets,
 * Token Streaming, Deep Thinking Accordion, Plugin Extension Hub,
 * Cascading Settings, and History Manager.
 */

const ALL_TOOLS = [
  "view_file",
  "write_file",
  "edit_file_exact",
  "list_dir",
  "grep_search",
  "run_command",
  "get_git_diff"
];

const TOOL_NAMES_CN = {
  view_file: "查看文件 (view_file)",
  write_file: "写入文件 (write_file)",
  edit_file_exact: "精准修改 (edit_file_exact)",
  list_dir: "列出目录 (list_dir)",
  grep_search: "全局检索 (grep_search)",
  run_command: "执行命令 (run_command)",
  get_git_diff: "变更对比 (get_git_diff)"
};

class AgentForgeClient {
  constructor() {
    this.ws = null;
    this.state = {
      workflow_state: "IDLE", // IDLE | RUNNING | PAUSED
      user_goal: "",
      current_round: 0,
      max_rounds: 10,
      current_speaker: "",
      agent_states: {},
      tasks: [],
      messages: [],
      config: null,
      workspace: "",
      active_slot_tab: 1,
      scroll_locked: true,
      current_stream_el: null,
      current_think_el: null,
      current_stream_sender: null,
    };

    this.initElements();
    this.initTheme();
    this.initMarkdown();
    this.bindEvents();
    this.initWebSocket();
  }

  initElements() {
    this.el = {
      globalStatusText: document.getElementById("global-status-text"),
      globalPulseDot: document.getElementById("global-pulse-dot"),
      globalRoundInfo: document.getElementById("global-round-info"),
      globalSpeakerBadge: document.getElementById("global-speaker-badge"),
      wsIndicator: document.getElementById("ws-indicator"),
      agentDeck: document.getElementById("agent-deck"),
      chatHistory: document.getElementById("chat-history"),
      goalInput: document.getElementById("goal-input"),
      btnRun: document.getElementById("btn-run-goal"),
      btnPause: document.getElementById("btn-pause-goal"),
      btnCancel: document.getElementById("btn-cancel-goal"),
      btnScrollLock: document.getElementById("btn-scroll-lock"),
      btnOpenSettings: document.getElementById("btn-open-settings"),
      btnOpenHistory: document.getElementById("btn-open-history"),
      btnOpenPlugins: document.getElementById("btn-open-plugins"),
      btnClearChat: document.getElementById("btn-clear-chat"),
      themeSelector: document.getElementById("theme-selector"),
      // Modals
      modalSettings: document.getElementById("modal-settings"),
      modalHistory: document.getElementById("modal-history"),
      modalPlugins: document.getElementById("modal-plugins"),
      modalFileViewer: document.getElementById("modal-file-viewer"),
      // Left panel tabs
      taskListContainer: document.getElementById("task-list-container"),
      fileListContainer: document.getElementById("file-list-container"),
      diffContentArea: document.getElementById("diff-content-area"),
      workspacePathLabel: document.getElementById("workspace-path-label"),
      // History elements
      historySessionList: document.getElementById("history-session-list"),
      historyPreviewPane: document.getElementById("history-preview-pane"),
      btnCopyHistoryMd: document.getElementById("btn-copy-history-md"),
      btnClearAllHistory: document.getElementById("btn-clear-all-history"),
      // Plugin elements
      pluginsContainer: document.getElementById("plugins-container"),
      // Toast container
      toastContainer: document.getElementById("toast-container"),
    };
  }

  initTheme() {
    const savedTheme = localStorage.getItem("agentforge_theme") || localStorage.getItem("opencode_theme") || "theme-cheese";
    document.body.className = savedTheme;
    if (this.el.themeSelector) {
      this.el.themeSelector.value = savedTheme;
      this.el.themeSelector.addEventListener("change", (e) => {
        const newTheme = e.target.value;
        document.body.className = newTheme;
        localStorage.setItem("agentforge_theme", newTheme);
        const themeNames = {
          "theme-cheese": "🧀 奶酪暖色",
          "theme-dark": "🌌 暗夜科技",
          "theme-latte": "☕ 燕麦拿铁",
          "theme-nordic": "🌿 极简雅白"
        };
        this.showToast(`已切换主题为: ${themeNames[newTheme] || newTheme}`, "success");
      });
    }
  }

  initMarkdown() {
    if (window.marked) {
      window.marked.setOptions({
        gfm: true,
        breaks: true,
        highlight: function(code, lang) {
          if (window.hljs && lang && window.hljs.getLanguage(lang)) {
            try {
              return window.hljs.highlight(code, { language: lang }).value;
            } catch (__) {}
          }
          if (window.hljs) {
            try {
              return window.hljs.highlightAuto(code).value;
            } catch (__) {}
          }
          return code;
        }
      });
    }
  }

  bindEvents() {
    // Dock Actions
    this.el.btnRun.addEventListener("click", () => this.handleRunAction());
    this.el.btnPause.addEventListener("click", () => this.handlePauseAction());
    this.el.btnCancel.addEventListener("click", () => this.handleCancelAction());
    this.el.btnClearChat.addEventListener("click", () => this.clearChatView());
    this.el.btnScrollLock.addEventListener("click", () => this.toggleScrollLock());

    // Input auto-resize & shortcut keys
    this.el.goalInput.addEventListener("input", (e) => {
      this.el.goalInput.style.height = "auto";
      this.el.goalInput.style.height = Math.min(this.el.goalInput.scrollHeight, 120) + "px";
    });

    this.el.goalInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (this.state.workflow_state === "IDLE" || this.state.workflow_state === "PAUSED") {
          this.handleRunAction();
        }
      }
    });

    // Global shortcut keys
    window.addEventListener("keydown", (e) => {
      if (e.key === "F1") {
        e.preventDefault();
        this.openSettingsModal();
      } else if (e.key === "F2") {
        e.preventDefault();
        this.openHistoryModal();
      } else if (e.ctrlKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        this.handlePauseAction();
      } else if (e.ctrlKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        this.clearChatView();
      } else if (e.key === "Escape") {
        this.closeAllModals();
      }
    });

    // Modal Triggers & Closers
    this.el.btnOpenSettings?.addEventListener("click", () => this.openSettingsModal());
    this.el.btnOpenHistory?.addEventListener("click", () => this.openHistoryModal());
    this.el.btnOpenPlugins?.addEventListener("click", () => this.openPluginsModal());

    document.querySelectorAll("[data-close]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const modalId = btn.getAttribute("data-close");
        document.getElementById(modalId)?.classList.remove("active");
      });
    });

    // Left Panel Tab Switching
    document.querySelectorAll(".panel-tabs .tab-btn[data-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        document.querySelectorAll(".panel-tabs .tab-btn[data-tab]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        document.getElementById("tab-content-tasks").style.display = (tab === "tasks") ? "block" : "none";
        document.getElementById("tab-content-files").style.display = (tab === "files") ? "block" : "none";
        document.getElementById("tab-content-diff").style.display = (tab === "diff") ? "block" : "none";

        if (tab === "files") this.loadWorkspaceFiles();
        if (tab === "diff") this.loadWorkspaceDiff();
      });
    });

    document.getElementById("btn-refresh-files")?.addEventListener("click", () => this.loadWorkspaceFiles());
    document.getElementById("btn-refresh-diff")?.addEventListener("click", () => this.loadWorkspaceDiff());
    document.getElementById("btn-copy-diff")?.addEventListener("click", () => {
      if (this.currentDiffRaw) {
        navigator.clipboard.writeText(this.currentDiffRaw).then(() => {
          this.showToast("✔ Git Diff 文本已复制到剪贴板", "success");
        });
      } else {
        this.showToast("暂无可复制的 Diff 内容", "info");
      }
    });

    // Settings Modal Tab Switching
    document.querySelectorAll("[data-cfg-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        // 切换主标签页前，立即自动把当前填写的供应商、槽位和工作区参数存入内存
        this.saveAllFormsToMemory();

        const tab = btn.getAttribute("data-cfg-tab");
        document.querySelectorAll("[data-cfg-tab]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        ["providers", "slots", "sandbox", "params"].forEach(t => {
          const contentEl = document.getElementById(`cfg-tab-content-${t}`);
          if (contentEl) contentEl.style.display = (t === tab) ? "block" : "none";
        });

        // 切换到 slots 标签页时，根据最新保存的 providers 重新渲染槽位 (保持下拉选项最新)
        if (tab === "slots") {
          this.renderSlotsSettings(this.state.active_slot_tab || 1);
        }
      });
    });

    document.getElementById("btn-save-settings")?.addEventListener("click", () => this.saveConfigSettings());
    document.getElementById("btn-add-provider")?.addEventListener("click", () => this.addCustomProviderUI());
    document.getElementById("btn-build-sandbox")?.addEventListener("click", () => this.buildSandboxEnv());
    this.el.btnClearAllHistory?.addEventListener("click", () => this.clearAllHistorySessions());
    this.el.btnCopyHistoryMd?.addEventListener("click", () => this.copyHistoryMarkdown());
  }

  // =========================================================================
  // WebSocket Communication
  // =========================================================================
  initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.el.wsIndicator.classList.remove("disconnected");
      this.el.wsIndicator.title = "WebSocket 实时连接正常";
      // Heartbeat
      if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = setInterval(() => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ command: "PING" }));
        }
      }, 10000);
    };

    this.ws.onclose = () => {
      this.el.wsIndicator.classList.add("disconnected");
      this.el.wsIndicator.title = "连接已断开，正在自动重连...";
      setTimeout(() => this.initWebSocket(), 2000);
    };

    this.ws.onerror = () => {
      this.el.wsIndicator.classList.add("disconnected");
    };

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        this.handleBusEvent(payload.event_type, payload.data);
      } catch (err) {
        console.error("解析 WS 消息异常:", err);
      }
    };
  }

  handleBusEvent(eventType, data) {
    switch (eventType) {
      case "INIT_STATE":
        this.handleInitState(data);
        break;
      case "TOKEN_STREAM":
        this.handleTokenStream(data);
        break;
      case "MESSAGE_LOGGED":
        this.handleMessageLogged(data);
        break;
      case "AGENT_STATE_CHANGED":
        this.handleAgentStateChanged(data);
        break;
      case "ROUND_UPDATED":
        this.handleRoundUpdated(data);
        break;
      case "TASK_ADDED":
      case "TASK_UPDATED":
        this.handleTaskUpdated(data);
        break;
      case "DIFF_UPDATED":
        this.loadWorkspaceDiff();
        break;
      case "WORKFLOW_PAUSED":
        this.setWorkflowState("PAUSED");
        this.showToast("⏸️ 工作流已中途暂停", "warning");
        break;
      case "WORKFLOW_RESUMED":
        this.setWorkflowState("RUNNING");
        this.showToast("▶️ 已解除暂停，继续接力", "success");
        break;
      case "GOAL_COMPLETED":
        this.setWorkflowState("IDLE");
        this.showToast("🎉 多 Agent 圆桌协同圆满达成目标！", "success");
        break;
      case "GOAL_FAILED":
        this.setWorkflowState("IDLE");
        this.showToast("⚠️ 任务结束或被中止", "warning");
        break;
      case "CONFIG_RELOADED":
        if (data.config) {
          this.state.config = data.config;
        } else {
          this.state.config = data;
        }
        if (data.agent_states) {
          this.state.agent_states = data.agent_states;
        }
        this.renderAgentDeck();
        break;
    }
  }

  handleInitState(data) {
    this.state.config = data.config;
    this.state.agent_states = data.agent_states || {};
    this.state.tasks = data.tasks || [];
    this.state.current_round = data.current_round || 0;
    this.state.max_rounds = data.max_rounds || 10;
    this.state.current_speaker = data.current_speaker || "";
    this.state.workspace = data.workspace || "";

    if (this.el.workspacePathLabel) {
      this.el.workspacePathLabel.textContent = `工作区: ${this.state.workspace}`;
    }

    this.renderAgentDeck();
    this.renderTaskList();
    this.updateHeaderProgress();
    this.setWorkflowState(data.workflow_state || "IDLE");

    // Render historical messages
    if (data.messages && data.messages.length > 0) {
      this.el.chatHistory.innerHTML = "";
      data.messages.forEach(msg => this.appendMessageCard(msg, false));
      this.scrollToBottom();
    }
  }

  // =========================================================================
  // Stream & Token Rendering
  // =========================================================================
  handleTokenStream(streamData) {
    const { slot_id, sender_name, sender_icon, token, is_thinking } = streamData;

    // If sender changed or stream container missing, create active card
    if (!this.state.current_stream_el || this.state.current_stream_sender !== sender_name) {
      this.state.current_stream_sender = sender_name;
      this.state.current_stream_el = this.createActiveStreamingCard(slot_id, sender_name, sender_icon);
    }

    const card = this.state.current_stream_el;

    if (is_thinking) {
      let thinkBlock = card.querySelector(".thinking-block");
      if (!thinkBlock) {
        thinkBlock = document.createElement("div");
        thinkBlock.className = "thinking-block expanded";
        thinkBlock.innerHTML = `
          <div class="thinking-summary">
            <div class="thinking-title">
              <span>🧠 深度思考过程</span>
              <span class="thinking-word-count">(0 字)</span>
            </div>
            <div class="thinking-stats">
              <span class="thinking-status">推理中...</span>
              <span class="chevron-icon">▼</span>
            </div>
          </div>
          <div class="thinking-content"></div>
        `;
        thinkBlock.querySelector(".thinking-summary").addEventListener("click", () => {
          thinkBlock.classList.toggle("expanded");
        });
        card.querySelector(".msg-body").before(thinkBlock);
      }

      const contentEl = thinkBlock.querySelector(".thinking-content");
      contentEl.textContent += token;
      const charCount = contentEl.textContent.length;
      thinkBlock.querySelector(".thinking-word-count").textContent = `(${charCount.toLocaleString()} 字)`;

    } else {
      // Body token
      let bodyEl = card.querySelector(".msg-body-content");
      if (!bodyEl) {
        bodyEl = document.createElement("div");
        bodyEl.className = "msg-body-content";
        card.querySelector(".msg-body").appendChild(bodyEl);
      }
      
      // Auto-collapse thinking block when body text begins
      const thinkBlock = card.querySelector(".thinking-block");
      if (thinkBlock && thinkBlock.classList.contains("expanded") && !thinkBlock.dataset.userToggled) {
        thinkBlock.classList.remove("expanded");
        const statusEl = thinkBlock.querySelector(".thinking-status");
        if (statusEl) statusEl.textContent = "思考完成";
      }

      if (!card.dataset.rawBody) card.dataset.rawBody = "";
      card.dataset.rawBody += token;

      // Render markdown
      if (window.marked) {
        bodyEl.innerHTML = window.marked.parse(card.dataset.rawBody);
      } else {
        bodyEl.textContent = card.dataset.rawBody;
      }
    }

    if (this.state.scroll_locked) {
      this.scrollToBottom();
    }
  }

  createActiveStreamingCard(slot_id, sender_name, sender_icon) {
    const card = document.createElement("div");
    card.className = "msg-card streaming-card";
    const nowStr = new Date().toTimeString().split(" ")[0];

    card.innerHTML = `
      <div class="msg-header">
        <div class="msg-sender-info">
          <span class="msg-avatar">${sender_icon || "🤖"}</span>
          <span class="msg-sender-name">${sender_name || "AI 成员"}</span>
          <span class="msg-badge">${slot_id || "streaming"}</span>
        </div>
        <span class="msg-time">${nowStr}</span>
      </div>
      <div class="msg-body">
        <div class="msg-body-content"></div>
        <span class="typing-cursor"></span>
      </div>
    `;

    this.el.chatHistory.appendChild(card);
    return card;
  }

  handleMessageLogged(msg) {
    // If we have an active stream card for this message, remove it cleanly so finalized card replaces it
    if (this.state.current_stream_el) {
      this.state.current_stream_el.remove();
      this.state.current_stream_el = null;
      this.state.current_stream_sender = null;
    }

    // Deduplicate by msg.id if already in DOM
    if (msg.id && this.el.chatHistory.querySelector(`[data-msg-id="${msg.id}"]`)) {
      return;
    }

    this.appendMessageCard(msg, true);
    if (this.state.scroll_locked) {
      this.scrollToBottom();
    }
  }

  appendMessageCard(msg, animate = true) {
    const card = document.createElement("div");
    card.className = `msg-card ${this.getCardClassForMsg(msg)}`;
    if (msg.id) card.dataset.msgId = msg.id;
    if (!animate) card.style.animation = "none";

    const timeStr = msg.timestamp ? new Date(msg.timestamp * 1000).toTimeString().split(" ")[0] : "";

    // Thinking Block
    let thinkHtml = "";
    if (msg.thinking_content) {
      const charCount = msg.thinking_content.length;
      thinkHtml = `
        <div class="thinking-block">
          <div class="thinking-summary">
            <div class="thinking-title">
              <span>🧠 深度思考记录</span>
              <span class="thinking-word-count">(${charCount.toLocaleString()} 字)</span>
            </div>
            <div class="thinking-stats">
              <span class="thinking-status">已折叠</span>
              <span class="chevron-icon">▼</span>
            </div>
          </div>
          <div class="thinking-content">${this.escapeHtml(msg.thinking_content)}</div>
        </div>
      `;
    }

    // Markdown parse body
    let bodyHtml = "";
    if (window.marked) {
      bodyHtml = window.marked.parse(msg.content || "");
    } else {
      bodyHtml = `<p>${this.escapeHtml(msg.content || "")}</p>`;
    }

    // Tool results
    let toolResultsHtml = "";
    if (msg.tool_results && msg.tool_results.length > 0) {
      toolResultsHtml = msg.tool_results.map(tr => {
        const outText = typeof tr === "object" ? (tr.output || JSON.stringify(tr, null, 2)) : String(tr);
        return `
          <div class="tool-call-box">
            <div class="tool-call-header">🛠️ 工具执行输出</div>
            <pre class="tool-result-box"><code>${this.escapeHtml(outText)}</code></pre>
          </div>
        `;
      }).join("");
    }

    card.innerHTML = `
      <div class="msg-header">
        <div class="msg-sender-info">
          <span class="msg-avatar">${msg.sender_icon || "💬"}</span>
          <span class="msg-sender-name">${msg.sender_name || msg.sender_id}</span>
          <span class="msg-badge">${msg.sender_id}</span>
        </div>
        <span class="msg-time">${timeStr}</span>
      </div>
      ${thinkHtml}
      <div class="msg-body">${bodyHtml}</div>
      ${toolResultsHtml}
    `;

    // Bind thinking accordion toggle
    const thinkToggle = card.querySelector(".thinking-summary");
    if (thinkToggle) {
      thinkToggle.addEventListener("click", () => {
        const block = card.querySelector(".thinking-block");
        block.classList.toggle("expanded");
      });
    }

    this.el.chatHistory.appendChild(card);
  }

  getCardClassForMsg(msg) {
    if (msg.msg_type === "goal") return "user-goal";
    if (msg.msg_type === "steering") return "steering";
    if (msg.msg_type === "vote") return "vote-card";
    if (msg.msg_type === "pause" || msg.msg_type === "error" || msg.sender_id === "system") return "system-notice";
    return "";
  }

  // =========================================================================
  // Agent Deck & Status Cards
  // =========================================================================
  renderAgentDeck() {
    if (!this.el.agentDeck) return;
    this.el.agentDeck.innerHTML = "";

    for (let i = 1; i <= 5; i++) {
      const slotId = `slot_${i}`;
      const state = this.state.agent_states[slotId] || {};
      const slotCfg = this.state.config?.agent_slots?.find(s => s.slot_id === slotId) || {};

      const isEnabled = slotCfg.enabled !== false;
      const status = isEnabled ? (state.status && state.status !== "DISABLED" ? state.status : "IDLE") : "DISABLED";
      const lastAction = isEnabled ? (state.last_action && !state.last_action.includes("未启用") ? state.last_action : "就绪待命") : "未启用 (Disabled)";

      let activeClass = "";
      if (!isEnabled || status === "DISABLED") {
        activeClass = "disabled";
      } else if (status === "SPEAKING") {
        activeClass = "active-speaking";
      } else if (status === "THINKING") {
        activeClass = "active-thinking";
      } else if (status === "EXECUTING_TOOL") {
        activeClass = "active-tool";
      }

      const card = document.createElement("div");
      card.className = `agent-card ${activeClass}`;
      card.innerHTML = `
        <div class="agent-avatar-wrap">
          <span>${slotCfg.icon || "🤖"}</span>
        </div>
        <div class="agent-details">
          <div class="agent-top-row">
            <span class="agent-name" title="${slotCfg.name || slotId}">${slotCfg.name || `槽位 ${i}`}</span>
            <span class="slot-tag">#${i}</span>
          </div>
          <div class="agent-model" title="${slotCfg.model || '-'}">${slotCfg.model || '-'}</div>
          <div class="agent-status-pill">${lastAction}</div>
        </div>
      `;

      card.addEventListener("click", () => {
        this.openSettingsModal("slots", i);
      });

      this.el.agentDeck.appendChild(card);
    }
  }

  handleAgentStateChanged(data) {
    const { slot_id, state } = data;
    this.state.agent_states[slot_id] = state;
    this.renderAgentDeck();
  }

  handleRoundUpdated(data) {
    this.state.current_round = data.round;
    this.state.max_rounds = data.max_rounds || this.state.max_rounds;
    if (data.speaker) this.state.current_speaker = data.speaker;
    this.updateHeaderProgress();
  }

  updateHeaderProgress() {
    if (this.state.current_round > 0) {
      this.el.globalRoundInfo.textContent = `第 ${this.state.current_round}/${this.state.max_rounds} 轮接力`;
      if (this.state.current_speaker) {
        this.el.globalSpeakerBadge.textContent = `· 当前发言: ${this.state.current_speaker}`;
      } else {
        this.el.globalSpeakerBadge.textContent = "";
      }
    } else {
      this.el.globalRoundInfo.textContent = "第 0 轮";
      this.el.globalSpeakerBadge.textContent = "";
    }
  }

  // =========================================================================
  // Workflow Control & Bottom Dock State
  // =========================================================================
  setWorkflowState(state) {
    this.state.workflow_state = state;

    if (state === "IDLE") {
      this.el.globalStatusText.textContent = "🟢 就绪待命";
      this.el.globalPulseDot.className = "pulse-dot";
      this.el.goalInput.placeholder = "💡 输入协同目标 (例如: 联合创作科幻小说第一章，作家起草，审核员润色)...";
      this.el.goalInput.disabled = false;

      this.el.btnRun.style.display = "inline-flex";
      this.el.btnRun.querySelector("span").textContent = "🚀 协同执行";
      this.el.btnPause.style.display = "none";
      this.el.btnCancel.style.display = "none";

    } else if (state === "RUNNING") {
      this.el.globalStatusText.textContent = "🔄 协同接力中";
      this.el.globalPulseDot.className = "pulse-dot running";
      this.el.goalInput.placeholder = "⏳ 多 Agent 正在轮流接力中... 可点击右侧 [⏸ 暂停/调整] 介入方向";
      this.el.goalInput.disabled = false;

      this.el.btnRun.style.display = "none";
      this.el.btnPause.style.display = "inline-flex";
      this.el.btnPause.querySelector("span").textContent = "⏸ 暂停/调整";
      this.el.btnCancel.style.display = "inline-flex";

    } else if (state === "PAUSED") {
      this.el.globalStatusText.textContent = "⏸️ 中途已暂停";
      this.el.globalPulseDot.className = "pulse-dot paused";
      this.el.goalInput.placeholder = "💡 请输入方向调整指导意见 (直接按 Enter 或点击继续)...";
      this.el.goalInput.disabled = false;

      this.el.btnRun.style.display = "inline-flex";
      this.el.btnRun.querySelector("span").textContent = "▶ 调整并继续";
      this.el.btnPause.style.display = "none";
      this.el.btnCancel.style.display = "inline-flex";
    }
  }

  async handleRunAction() {
    const text = this.el.goalInput.value.trim();

    if (this.state.workflow_state === "IDLE") {
      if (!text) {
        this.showToast("请输入开发或创作总目标", "warning");
        this.el.goalInput.focus();
        return;
      }
      this.el.goalInput.value = "";
      this.setWorkflowState("RUNNING");
      try {
        const res = await fetch("/api/action/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ goal: text })
        });
        if (!res.ok) {
          const err = await res.json();
          this.showToast(`启动失败: ${err.detail}`, "error");
          this.setWorkflowState("IDLE");
        }
      } catch (e) {
        this.showToast(`网络异常: ${e}`, "error");
        this.setWorkflowState("IDLE");
      }

    } else if (this.state.workflow_state === "PAUSED") {
      this.el.goalInput.value = "";
      this.setWorkflowState("RUNNING");
      try {
        await fetch("/api/action/resume", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ feedback: text })
        });
      } catch (e) {
        this.showToast(`恢复异常: ${e}`, "error");
      }
    }
  }

  async handlePauseAction() {
    if (this.state.workflow_state === "RUNNING") {
      try {
        await fetch("/api/action/pause", { method: "POST" });
      } catch (e) {
        this.showToast(`暂停失败: ${e}`, "error");
      }
    } else if (this.state.workflow_state === "PAUSED") {
      this.handleRunAction();
    }
  }

  async handleCancelAction() {
    if (confirm("确定要彻底终止当前正在进行的圆桌协同任务吗？")) {
      try {
        await fetch("/api/action/cancel", { method: "POST" });
        this.setWorkflowState("IDLE");
        this.showToast("已请求终止协同流程", "warning");
      } catch (e) {
        this.showToast(`终止失败: ${e}`, "error");
      }
    }
  }

  // =========================================================================
  // Plugins Hub Modal
  // =========================================================================
  async openPluginsModal() {
    try {
      const res = await fetch("/api/plugins");
      const data = await res.json();
      const plugins = data.plugins || [];
      this.renderPluginsList(plugins);
      this.openModal("modal-plugins");
    } catch (e) {
      this.showToast(`获取插件列表失败: ${e}`, "error");
    }
  }

  renderPluginsList(plugins) {
    if (!this.el.pluginsContainer) return;
    this.el.pluginsContainer.innerHTML = "";

    plugins.forEach(p => {
      const card = document.createElement("div");
      card.className = "plugin-card";
      card.innerHTML = `
        <div>
          <div class="plugin-header">
            <div class="plugin-info">
              <span class="plugin-icon">${p.icon || '🧩'}</span>
              <div>
                <div class="plugin-title">${p.name}</div>
                <div class="plugin-ver">v${p.version} · ${p.author}</div>
              </div>
            </div>
            <label class="switch-toggle" title="${p.enabled ? '点击禁用' : '点击启用'}">
              <input type="checkbox" data-plugin-id="${p.id}" ${p.enabled ? 'checked' : ''}>
              <span class="switch-slider"></span>
            </label>
          </div>
          <div class="plugin-desc" style="margin-top:0.5rem;">${p.description}</div>
        </div>
      `;

      const toggleInput = card.querySelector("input[data-plugin-id]");
      toggleInput.addEventListener("change", async (e) => {
        const isChecked = e.target.checked;
        try {
          const toggleRes = await fetch(`/api/plugins/${p.id}/toggle`, { method: "POST" });
          const resData = await toggleRes.json();
          if (resData.status === "ok") {
            this.showToast(`${p.icon} ${p.name} 已${isChecked ? '启用' : '禁用'}`, "success");
          }
        } catch (err) {
          this.showToast(`操作插件异常: ${err}`, "error");
          e.target.checked = !isChecked;
        }
      });

      this.el.pluginsContainer.appendChild(card);
    });
  }

  // =========================================================================
  // Left Panel: Tasks, Files, Diff
  // =========================================================================
  handleTaskUpdated(task) {
    const existingIdx = this.state.tasks.findIndex(t => t.id === task.id);
    if (existingIdx >= 0) {
      this.state.tasks[existingIdx] = task;
    } else {
      this.state.tasks.push(task);
    }
    this.renderTaskList();
  }

  renderTaskList() {
    if (!this.el.taskListContainer) return;
    if (this.state.tasks.length === 0) {
      this.el.taskListContainer.innerHTML = `
        <div class="empty-state" style="text-align:center; color:var(--text-muted); padding:2rem 0;">
          暂无协同任务，输入总目标后将自动分解推进
        </div>
      `;
      return;
    }

    this.el.taskListContainer.innerHTML = "";
    this.state.tasks.forEach(t => {
      const card = document.createElement("div");
      const statusLower = (t.status || "pending").toLowerCase();
      card.className = `task-item ${statusLower}`;

      let statusBadgeCn = "待处理";
      if (t.status === "IN_PROGRESS") statusBadgeCn = "进行中";
      else if (t.status === "COMPLETED") statusBadgeCn = "✔ 已完成";
      else if (t.status === "FAILED") statusBadgeCn = "❌ 失败";

      card.innerHTML = `
        <div class="task-header">
          <span class="task-title">${t.title || "协同任务"}</span>
          <span class="task-status-badge ${statusLower}">${statusBadgeCn}</span>
        </div>
        <div class="task-assignee">👤 负责人: ${t.assigned_name || t.assigned_slot_id}</div>
        ${t.description ? `<div class="task-desc">${t.description}</div>` : ""}
      `;
      this.el.taskListContainer.appendChild(card);
    });
  }

  async loadWorkspaceFiles() {
    try {
      const res = await fetch("/api/files");
      const data = await res.json();
      if (data.status === "ok" && this.el.fileListContainer) {
        this.el.fileListContainer.innerHTML = "";
        if (data.items.length === 0) {
          this.el.fileListContainer.innerHTML = `<div style="color:var(--text-muted); padding:1rem; text-align:center;">工作区暂无文件</div>`;
          return;
        }
        data.items.forEach(file => {
          const row = document.createElement("div");
          row.className = "file-row";
          const icon = file.is_dir ? "📁" : "📄";
          const sizeKb = (file.size / 1024).toFixed(1);
          row.innerHTML = `
            <span>${icon} ${file.name}</span>
            <span style="color:var(--text-muted); font-size:0.7rem;">${file.is_dir ? '目录' : sizeKb + ' KB'}</span>
          `;
          if (!file.is_dir) {
            row.addEventListener("click", () => this.openFileViewer(file.rel_path));
          }
          this.el.fileListContainer.appendChild(row);
        });
      }
    } catch (e) {
      console.error("加载文件列表失败:", e);
    }
  }

  async openFileViewer(relPath) {
    try {
      const res = await fetch(`/api/files/read?path=${encodeURIComponent(relPath)}`);
      const data = await res.json();
      if (data.status === "ok") {
        document.getElementById("file-viewer-title").textContent = `📄 ${relPath}`;
        const codeEl = document.getElementById("file-viewer-code");
        codeEl.textContent = data.content;
        if (window.hljs) {
          window.hljs.highlightElement(codeEl);
        }
        this.openModal("modal-file-viewer");
      } else {
        this.showToast(`打开文件失败: ${data.detail}`, "error");
      }
    } catch (e) {
      this.showToast(`读取文件失败: ${e}`, "error");
    }
  }

  parseUnifiedDiff(diffText) {
    if (!diffText || typeof diffText !== "string") return null;

    // Check if it is informational notice
    if (diffText.includes("未初始化 Git") || diffText.includes("暂无未提交变动") || diffText.includes("工作区就绪，暂无") || diffText.includes("Working tree clean")) {
      return { isNotice: true, message: diffText };
    }

    const lines = diffText.split("\n");
    const files = [];
    let currentFile = null;
    let currentChunk = null;
    let oldLine = 0;
    let newLine = 0;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.startsWith("diff --git ")) {
        const parts = line.split(" ");
        const pathA = parts[2] ? parts[2].replace(/^a\//, '') : '';
        const pathB = parts[3] ? parts[3].replace(/^b\//, '') : '';
        const filename = pathB || pathA || "unknown";

        currentFile = {
          filename: filename,
          oldPath: pathA,
          newPath: pathB,
          additions: 0,
          deletions: 0,
          chunks: []
        };
        files.push(currentFile);
        currentChunk = null;
        continue;
      }

      if (!currentFile) continue;

      if (line.startsWith("@@ ")) {
        const match = line.match(/@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@(.*)/);
        if (match) {
          oldLine = parseInt(match[1], 10);
          newLine = parseInt(match[2], 10);
        }
        currentChunk = {
          header: line,
          lines: []
        };
        currentFile.chunks.push(currentChunk);
        continue;
      }

      if (!currentChunk) continue;

      if (line.startsWith("+") && !line.startsWith("+++")) {
        currentFile.additions++;
        currentChunk.lines.push({
          type: "add",
          oldNum: "",
          newNum: newLine++,
          prefix: "+",
          content: line.substring(1)
        });
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        currentFile.deletions++;
        currentChunk.lines.push({
          type: "del",
          oldNum: oldLine++,
          newNum: "",
          prefix: "-",
          content: line.substring(1)
        });
      } else if (!line.startsWith("\\ No newline")) {
        currentChunk.lines.push({
          type: "ctx",
          oldNum: oldLine++,
          newNum: newLine++,
          prefix: " ",
          content: line.startsWith(" ") ? line.substring(1) : line
        });
      }
    }

    if (files.length === 0) {
      return { isNotice: true, message: diffText };
    }

    return { isNotice: false, files: files };
  }

  async loadWorkspaceDiff() {
    const container = document.getElementById("diff-view-container");
    const filesCountBadge = document.getElementById("diff-files-count");
    const addCountBadge = document.getElementById("diff-additions-count");
    const delCountBadge = document.getElementById("diff-deletions-count");
    if (!container) return;

    try {
      const res = await fetch("/api/diff");
      const data = await res.json();
      const rawDiff = data.diff || "";
      this.currentDiffRaw = rawDiff;

      const parsed = this.parseUnifiedDiff(rawDiff);

      if (!parsed || parsed.isNotice) {
        if (filesCountBadge) filesCountBadge.textContent = "0 个文件变更";
        if (addCountBadge) addCountBadge.style.display = "none";
        if (delCountBadge) delCountBadge.style.display = "none";

        const noticeText = parsed?.message || "当前工作区暂无未提交改动 (Working tree clean)";
        container.innerHTML = `
          <div class="diff-empty-card">
            <div class="diff-empty-icon">🌿</div>
            <div class="diff-empty-title">工作区整洁 (Clean Tree)</div>
            <div class="diff-empty-desc">${this.escapeHtml(noticeText)}</div>
          </div>
        `;
        return;
      }

      let totalAdd = 0;
      let totalDel = 0;
      parsed.files.forEach(f => {
        totalAdd += f.additions;
        totalDel += f.deletions;
      });

      if (filesCountBadge) filesCountBadge.textContent = `${parsed.files.length} 个文件变更`;
      if (addCountBadge) {
        addCountBadge.textContent = `+${totalAdd}`;
        addCountBadge.style.display = "inline-block";
      }
      if (delCountBadge) {
        delCountBadge.textContent = `-${totalDel}`;
        delCountBadge.style.display = "inline-block";
      }

      container.innerHTML = "";

      parsed.files.forEach(file => {
        const fileCard = document.createElement("div");
        fileCard.className = "diff-file-card";

        let linesHtml = "";
        file.chunks.forEach(chunk => {
          linesHtml += `<div class="diff-hunk-header">${this.escapeHtml(chunk.header)}</div>`;
          chunk.lines.forEach(l => {
            linesHtml += `
              <div class="diff-line ${l.type}">
                <span class="diff-line-num">${l.oldNum || ''}</span>
                <span class="diff-line-num">${l.newNum || ''}</span>
                <span class="diff-line-prefix">${l.prefix}</span>
                <span class="diff-line-content">${this.escapeHtml(l.content)}</span>
              </div>
            `;
          });
        });

        fileCard.innerHTML = `
          <div class="diff-file-header">
            <div class="diff-file-title">
              <span>📄</span>
              <span>${file.filename}</span>
            </div>
            <div class="diff-file-meta">
              <span style="color:var(--accent-success); font-weight:600;">+${file.additions}</span>
              <span style="color:var(--accent-danger); font-weight:600;">-${file.deletions}</span>
              <span class="chevron-icon" style="font-size:0.7rem;">▼</span>
            </div>
          </div>
          <div class="diff-file-body">${linesHtml}</div>
        `;

        const headerEl = fileCard.querySelector(".diff-file-header");
        headerEl.addEventListener("click", () => {
          fileCard.classList.toggle("collapsed");
          const icon = fileCard.querySelector(".chevron-icon");
          if (icon) {
            icon.textContent = fileCard.classList.contains("collapsed") ? "▶" : "▼";
          }
        });

        container.appendChild(fileCard);
      });

    } catch (e) {
      container.innerHTML = `<div style="color:var(--accent-danger); padding:1rem; text-align:center;">获取 Diff 异常: ${e}</div>`;
    }
  }

  // =========================================================================
  // Settings Modal (F1)
  // =========================================================================
  async openSettingsModal(defaultTab = "providers", defaultSlot = 1) {
    try {
      const res = await fetch("/api/config");
      this.state.config = await res.json();
      this.renderProvidersSettings();
      this.renderSlotsSettings(defaultSlot);
      this.renderSandboxSettings();
      this.renderParamsSettings();

      // Switch tab
      document.querySelectorAll("[data-cfg-tab]").forEach(b => {
        b.classList.toggle("active", b.getAttribute("data-cfg-tab") === defaultTab);
      });
      ["providers", "slots", "sandbox", "params"].forEach(t => {
        const el = document.getElementById(`cfg-tab-content-${t}`);
        if (el) el.style.display = (t === defaultTab) ? "block" : "none";
      });

      this.openModal("modal-settings");
    } catch (e) {
      this.showToast(`读取配置失败: ${e}`, "error");
    }
  }

  renderProvidersSettings() {
    const container = document.getElementById("providers-container");
    if (!container || !this.state.config) return;
    container.innerHTML = "";

    this.state.config.providers.forEach((prov, idx) => {
      const box = document.createElement("div");
      box.style.cssText = "background:var(--bg-primary); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:0.85rem;";
      box.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
          <div style="font-weight:600; color:var(--text-primary);">🏷️ ${prov.name} <span style="font-size:0.75rem; color:var(--text-muted); font-weight:normal;">(${prov.id})</span></div>
          ${idx >= 5 ? `<button class="danger-btn" style="padding:0.2rem 0.5rem; font-size:0.7rem;" data-del-prov="${prov.id}">删除</button>` : ""}
        </div>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.6rem; margin-bottom:0.5rem;">
          <div>
            <label class="form-label" style="font-size:0.75rem;">Base URL</label>
            <input type="text" class="form-input prov-base-url" data-prov-id="${prov.id}" value="${prov.base_url}">
          </div>
          <div>
            <label class="form-label" style="font-size:0.75rem;">API Key</label>
            <input type="password" class="form-input prov-api-key" data-prov-id="${prov.id}" value="${prov.api_key}" placeholder="sk-...">
          </div>
        </div>
        <div>
          <label class="form-label" style="font-size:0.75rem;">预设/可用模型清单 (英文逗号分隔)</label>
          <input type="text" class="form-input prov-models" data-prov-id="${prov.id}" value="${(prov.models || []).join(', ')}">
        </div>
      `;

      const delBtn = box.querySelector("[data-del-prov]");
      if (delBtn) {
        delBtn.addEventListener("click", () => {
          this.saveProvidersFormToMemory();
          this.state.config.providers = this.state.config.providers.filter(p => p.id !== prov.id);
          this.renderProvidersSettings();
        });
      }

      container.appendChild(box);
    });
  }

  saveProvidersFormToMemory() {
    if (!this.state.config?.providers) return;
    document.querySelectorAll(".prov-base-url").forEach(input => {
      const id = input.getAttribute("data-prov-id");
      const prov = this.state.config.providers.find(p => p.id === id);
      if (prov) prov.base_url = input.value.trim();
    });
    document.querySelectorAll(".prov-api-key").forEach(input => {
      const id = input.getAttribute("data-prov-id");
      const prov = this.state.config.providers.find(p => p.id === id);
      if (prov) prov.api_key = input.value.trim();
    });
    document.querySelectorAll(".prov-models").forEach(input => {
      const id = input.getAttribute("data-prov-id");
      const prov = this.state.config.providers.find(p => p.id === id);
      if (prov) {
        prov.models = input.value.split(",").map(m => m.trim()).filter(Boolean);
      }
    });
  }

  addCustomProviderUI() {
    this.saveProvidersFormToMemory();
    const id = prompt("请输入新供应商英文标识 (如 custom_llm):")?.trim();
    if (!id) return;
    const name = prompt("请输入供应商展示名称 (如 自定义模型网关):")?.trim() || id;

    this.state.config.providers.push({
      id: id,
      name: name,
      base_url: "https://api.openai.com/v1",
      api_key: "",
      models: ["default-model"]
    });
    this.renderProvidersSettings();
  }

  renderSlotsSettings(activeSlotIndex = 1) {
    const subtabs = document.getElementById("slots-subtabs");
    const container = document.getElementById("slot-form-container");
    if (!subtabs || !container || !this.state.config) return;

    // 切换槽位子标签前，先自动把前一个槽位的所有表单内容存入内存
    this.saveCurrentSlotFormToMemory();

    this.state.active_slot_tab = activeSlotIndex;
    subtabs.innerHTML = "";

    for (let i = 1; i <= 5; i++) {
      const slotCfg = this.state.config.agent_slots.find(s => s.slot_index === i);
      const btn = document.createElement("button");
      btn.className = `tab-btn ${i === activeSlotIndex ? 'active' : ''}`;
      btn.textContent = `${slotCfg ? slotCfg.icon : '🤖'} 槽位 ${i}`;
      btn.addEventListener("click", () => this.renderSlotsSettings(i));
      subtabs.appendChild(btn);
    }

    const currentSlot = this.state.config.agent_slots.find(s => s.slot_index === activeSlotIndex);
    if (!currentSlot) return;

    // Provider Options
    const provOptionsHtml = this.state.config.providers.map(p =>
      `<option value="${p.id}" ${p.id === currentSlot.provider_id ? 'selected' : ''}>${p.name}</option>`
    ).join("");

    // Selected provider's models
    const selectedProv = this.state.config.providers.find(p => p.id === currentSlot.provider_id) || this.state.config.providers[0];
    const modelOptionsHtml = (selectedProv?.models || ["deepseek-chat"]).map(m =>
      `<option value="${m}" ${m === currentSlot.model ? 'selected' : ''}>${m}</option>`
    ).join("");

    // Tool Checkboxes
    const toolCheckboxesHtml = ALL_TOOLS.map(t => {
      const checked = (currentSlot.allowed_tools || []).includes(t) ? "checked" : "";
      return `
        <label style="display:inline-flex; align-items:center; gap:0.3rem; font-size:0.75rem; color:var(--text-secondary); margin-right:0.75rem; margin-bottom:0.35rem; cursor:pointer;">
          <input type="checkbox" class="slot-tool-cb" value="${t}" ${checked}> ${TOOL_NAMES_CN[t] || t}
        </label>
      `;
    }).join("");

    container.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
        <label style="display:inline-flex; align-items:center; gap:0.5rem; font-weight:600; cursor:pointer; color:var(--text-primary);">
          <input type="checkbox" id="slot-enabled-cb" ${currentSlot.enabled ? 'checked' : ''}>
          <span>启用该成员槽位 (Enabled)</span>
        </label>
        <span style="font-size:0.75rem; color:var(--text-muted);">槽位标识: ${currentSlot.slot_id}</span>
      </div>

      <div style="display:grid; grid-template-columns: 80px 1fr 1fr; gap:0.6rem; margin-bottom:0.75rem;">
        <div>
          <label class="form-label" style="font-size:0.75rem;">图标</label>
          <input type="text" id="slot-icon-input" class="form-input" value="${currentSlot.icon || '✍️'}" style="text-align:center;">
        </div>
        <div>
          <label class="form-label" style="font-size:0.75rem;">角色名称</label>
          <input type="text" id="slot-name-input" class="form-input" value="${currentSlot.name}">
        </div>
        <div>
          <label class="form-label" style="font-size:0.75rem;">思考模式 (Thinking Mode)</label>
          <select id="slot-thinking-select" class="form-select">
            <option value="deep" ${currentSlot.thinking_mode === 'deep' ? 'selected' : ''}>🧠 深度思考 (Deep)</option>
            <option value="lite" ${currentSlot.thinking_mode === 'lite' ? 'selected' : ''}>⚡ 轻度思考 (Lite - 1024 Token)</option>
            <option value="off" ${currentSlot.thinking_mode === 'off' ? 'selected' : ''}>🚀 关闭思考 (极速出字)</option>
          </select>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.6rem; margin-bottom:0.75rem;">
        <div>
          <label class="form-label" style="font-size:0.75rem;">绑定 API 供应商</label>
          <select id="slot-provider-select" class="form-select">
            ${provOptionsHtml}
          </select>
        </div>
        <div>
          <label class="form-label" style="font-size:0.75rem;">绑定大模型 (Model)</label>
          <select id="slot-model-select" class="form-select">
            ${modelOptionsHtml}
          </select>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label" style="font-size:0.75rem;">允许调用的沙箱工具</label>
        <div style="background:var(--bg-primary); padding:0.5rem 0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
          ${toolCheckboxesHtml}
        </div>
      </div>

      <div class="form-group">
        <label class="form-label" style="font-size:0.75rem;">角色职责与系统提示词 (System Prompt)</label>
        <textarea id="slot-prompt-input" class="form-textarea" rows="4">${currentSlot.system_prompt}</textarea>
      </div>
    `;

    // Cascade Provider -> Model
    const provSelect = document.getElementById("slot-provider-select");
    const modelSelect = document.getElementById("slot-model-select");
    provSelect.addEventListener("change", () => {
      const p = this.state.config.providers.find(x => x.id === provSelect.value);
      const models = p?.models || ["deepseek-chat"];
      modelSelect.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join("");
    });
  }

  saveCurrentSlotFormToMemory() {
    const slotIdx = this.state.active_slot_tab;
    const currentSlot = this.state.config?.agent_slots?.find(s => s.slot_index === slotIdx);
    if (!currentSlot) return;

    const enabledCb = document.getElementById("slot-enabled-cb");
    const iconInput = document.getElementById("slot-icon-input");
    const nameInput = document.getElementById("slot-name-input");
    const thinkingSelect = document.getElementById("slot-thinking-select");
    const provSelect = document.getElementById("slot-provider-select");
    const modelSelect = document.getElementById("slot-model-select");
    const promptInput = document.getElementById("slot-prompt-input");

    if (enabledCb) currentSlot.enabled = enabledCb.checked;
    if (iconInput) currentSlot.icon = iconInput.value.trim() || "🤖";
    if (nameInput) currentSlot.name = nameInput.value.trim();
    if (thinkingSelect) currentSlot.thinking_mode = thinkingSelect.value;
    if (provSelect) currentSlot.provider_id = provSelect.value;
    if (modelSelect) currentSlot.model = modelSelect.value;
    if (promptInput) currentSlot.system_prompt = promptInput.value.trim();

    const checkedTools = [];
    document.querySelectorAll(".slot-tool-cb:checked").forEach(cb => checkedTools.push(cb.value));
    currentSlot.allowed_tools = checkedTools;
  }

  renderSandboxSettings() {
    document.getElementById("cfg-workspace-root").value = this.state.config.workspace_root || "";
    this.checkSandboxEnv();
  }

  async checkSandboxEnv() {
    try {
      const res = await fetch("/api/sandbox/check");
      const data = await res.json();
      const statusText = document.getElementById("sandbox-status-text");
      const pathText = document.getElementById("sandbox-path-text");

      if (data.ready) {
        statusText.innerHTML = `<span style="color:var(--accent-success);">✔ 隔离沙箱环境正常就绪</span>`;
        pathText.textContent = `Python 解释器: ${data.python_path}`;
      } else {
        statusText.innerHTML = `<span style="color:var(--accent-warning);">⚠️ 隔离沙箱环境未构建</span>`;
        pathText.textContent = `沙箱目录: ${data.sandbox_env_dir}`;
      }
    } catch (e) {
      console.error("检查沙箱失败:", e);
    }
  }

  async buildSandboxEnv() {
    const btn = document.getElementById("btn-build-sandbox");
    btn.disabled = true;
    btn.textContent = "⏳ 正在构建虚拟环境中...";
    try {
      const res = await fetch("/api/sandbox/build", { method: "POST" });
      const data = await res.json();
      if (data.ready) {
        this.showToast("✔ AI 独立测试沙箱环境已成功就绪！", "success");
      } else {
        this.showToast(`构建沙箱失败: ${data.message}`, "error");
      }
      this.checkSandboxEnv();
    } catch (e) {
      this.showToast(`构建请求异常: ${e}`, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "🔨 一键重新构建独立沙箱";
    }
  }

  renderParamsSettings() {
    document.getElementById("cfg-max-loops").value = this.state.config.max_loops_per_task || 10;
    document.getElementById("cfg-command-timeout").value = this.state.config.command_timeout_seconds || 60;
  }

  saveWorkspaceAndParamsToMemory() {
    if (!this.state.config) return;
    const wsInput = document.getElementById("cfg-workspace-root");
    if (wsInput) this.state.config.workspace_root = wsInput.value.trim();

    const maxLoopsInput = document.getElementById("cfg-max-loops");
    if (maxLoopsInput) this.state.config.max_loops_per_task = parseInt(maxLoopsInput.value) || 10;

    const timeoutInput = document.getElementById("cfg-command-timeout");
    if (timeoutInput) this.state.config.command_timeout_seconds = parseInt(timeoutInput.value) || 60;
  }

  saveAllFormsToMemory() {
    this.saveProvidersFormToMemory();
    this.saveCurrentSlotFormToMemory();
    this.saveWorkspaceAndParamsToMemory();
  }

  async saveConfigSettings() {
    // 收集所有标签页与槽位的全量输入存入内存对象
    this.saveAllFormsToMemory();

    // Send POST
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.state.config)
      });
      const data = await res.json();
      if (data.status === "ok") {
        this.state.config = data.config;
        if (data.agent_states) {
          this.state.agent_states = data.agent_states;
        }
        this.renderAgentDeck();
        this.closeAllModals();
        this.showToast("✔ 多 API 供应商与角色配置已成功保存！", "success");
      } else {
        this.showToast(`保存失败: ${data.detail}`, "error");
      }
    } catch (e) {
      this.showToast(`保存异常: ${e}`, "error");
    }
  }

  // =========================================================================
  // History Modal (F2)
  // =========================================================================
  async openHistoryModal() {
    try {
      const res = await fetch("/api/history");
      const data = await res.json();
      const sessions = data.sessions || [];
      this.renderHistoryList(sessions);
      this.openModal("modal-history");
    } catch (e) {
      this.showToast(`获取历史会话失败: ${e}`, "error");
    }
  }

  renderHistoryList(sessions) {
    if (!this.el.historySessionList) return;
    this.el.historySessionList.innerHTML = "";

    if (sessions.length === 0) {
      this.el.historySessionList.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding:2rem 0;">暂无历史会话记录</div>`;
      this.el.historyPreviewPane.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding:4rem 0;">暂无记录</div>`;
      this.el.btnCopyHistoryMd.style.display = "none";
      return;
    }

    sessions.forEach((s, idx) => {
      const card = document.createElement("div");
      card.className = `history-card ${idx === 0 ? 'active' : ''}`;
      card.innerHTML = `
        <div style="font-weight:600; font-size:0.8rem; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
          ${s.goal || '未命名协同'}
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.35rem; font-size:0.7rem; color:var(--text-muted);">
          <span>${s.date_str || s.session_id}</span>
          <span style="color:${s.success ? 'var(--accent-success)' : 'var(--accent-warning)'};">
            ${s.success ? '✔ 达成' : '❌ 未完'} (${s.total_rounds} 轮)
          </span>
        </div>
      `;

      card.addEventListener("click", () => {
        document.querySelectorAll(".history-card").forEach(c => c.classList.remove("active"));
        card.classList.add("active");
        this.loadSessionDetail(s.session_id);
      });

      this.el.historySessionList.appendChild(card);
    });

    if (sessions.length > 0) {
      this.loadSessionDetail(sessions[0].session_id);
    }
  }

  async loadSessionDetail(sessionId) {
    try {
      const res = await fetch(`/api/history/${sessionId}`);
      const data = await res.json();
      if (data.status === "ok") {
        this.currentSessionMd = data.markdown;
        if (window.marked) {
          this.el.historyPreviewPane.innerHTML = window.marked.parse(data.markdown);
        } else {
          this.el.historyPreviewPane.textContent = data.markdown;
        }
        this.el.btnCopyHistoryMd.style.display = "inline-flex";
      }
    } catch (e) {
      this.el.historyPreviewPane.textContent = `加载失败: ${e}`;
    }
  }

  copyHistoryMarkdown() {
    if (this.currentSessionMd) {
      navigator.clipboard.writeText(this.currentSessionMd).then(() => {
        this.showToast("✔ Markdown 纪要已复制到剪贴板", "success");
      });
    }
  }

  async clearAllHistorySessions() {
    if (confirm("确定要清空删除所有已归档的历史会话与纪要吗？此操作不可恢复！")) {
      try {
        await fetch("/api/history", { method: "DELETE" });
        this.showToast("已清空所有历史记录", "success");
        this.openHistoryModal();
      } catch (e) {
        this.showToast(`清空失败: ${e}`, "error");
      }
    }
  }

  // =========================================================================
  // Utilities
  // =========================================================================
  openModal(modalId) {
    document.getElementById(modalId)?.classList.add("active");
  }

  closeAllModals() {
    document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
  }

  clearChatView() {
    this.el.chatHistory.innerHTML = `
      <div class="msg-card system-notice">
        <div class="msg-body" style="font-size:0.8rem; color:var(--text-muted); text-align:center;">
          🧹 屏幕历史已清空 (后台完整数据保持完好)
        </div>
      </div>
    `;
  }

  toggleScrollLock() {
    this.state.scroll_locked = !this.state.scroll_locked;
    this.el.btnScrollLock.querySelector("span").textContent = this.state.scroll_locked ? "⬇️ 锁定滚动" : "🔓 自由滚动";
    if (this.state.scroll_locked) {
      this.scrollToBottom();
    }
  }

  scrollToBottom() {
    if (this.el.chatHistory) {
      this.el.chatHistory.scrollTop = this.el.chatHistory.scrollHeight;
    }
  }

  showToast(message, type = "info") {
    if (!this.el.toastContainer) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    this.el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
}

// Instantiate on load
window.addEventListener("DOMContentLoaded", () => {
  window.app = new AgentForgeClient();
});
