/* ==========================================================================
   SENA — AI KNOWLEDGE SEARCH HUB CLIENT LOGIC (v3.0)
   Hybrid Semantic Retrieval • Real-time SSE • Instant Smart Answer • Reader
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let allFiles = [];
  let foldersData = [];
  let currentSearchResults = [];
  let isSearching = false;
  let currentSort = "relevance"; // 'relevance' | 'date'
  let sseSource = null;
  let activeReaderFileId = null;

  // DOM Elements - Search & Header
  const searchInput = document.getElementById("search-input");
  const btnSubmitSearch = document.getElementById("btn-submit-search");
  const btnClearSearch = document.getElementById("btn-clear-search");
  const resultsBar = document.getElementById("results-bar");
  const resultsCount = document.getElementById("results-count");
  const resultsLatency = document.getElementById("results-latency");
  const btnBackDashboard = document.getElementById("btn-back-dashboard");
  const explorerViewContainer = document.getElementById("explorer-view-container");

  // Smart Answer Card & Perplexity UI Elements
  const smartAnswerBox = document.getElementById("smart-answer-box");
  const smartAnswerQuote = document.getElementById("smart-answer-quote");
  const smartAnswerRelevance = document.getElementById("smart-answer-relevance");
  const smartSourceTitle = document.getElementById("smart-source-title");
  const smartSourcePage = document.getElementById("smart-source-page");
  const btnSmartOpen = document.getElementById("btn-smart-open");
  const btnSmartReveal = document.getElementById("btn-smart-reveal");
  const btnSmartCopy = document.getElementById("btn-smart-copy");
  let currentSmartFileId = null;
  let currentSmartText = "";

  // Perplexity-style AI Summary Elements
  const toggleAutoSummary = document.getElementById("toggle-auto-summary");
  const perplexitySourcesList = document.getElementById("perplexity-sources-list");
  const perplexitySummaryBody = document.getElementById("perplexity-summary-body");
  const btnCopySummary = document.getElementById("btn-copy-summary");
  const btnRefreshSummary = document.getElementById("btn-refresh-summary");
  const btnToggleSummaryCollapse = document.getElementById("btn-toggle-summary-collapse");
  const summaryCollapseIcon = document.getElementById("summary-collapse-icon");
  const resultsDividerLabel = document.getElementById("results-divider-label");

  let isAutoSummaryEnabled = localStorage.getItem("sena_auto_summary") !== "false";
  let activeSummaryAbortController = null;
  let lastSearchQuery = "";
  let currentTopResults = [];
  let currentSynthesizedText = "";
  let currentActiveModelDisplayName = "⚡ Qwen 2.5 0.5B (468 MB)";

  // Filter & Sort Pills
  const formatPills = document.querySelectorAll(".format-pill");
  const filterPdf = document.getElementById("filter-pdf");
  const filterDocx = document.getElementById("filter-docx");
  const filterTxt = document.getElementById("filter-txt");
  const sortRelevance = document.getElementById("sort-relevance");
  const sortDate = document.getElementById("sort-date");
  const topicChips = document.getElementById("topic-chips");

  // Modals & Navigation
  const btnAddFolderModal = document.getElementById("btn-add-folder-modal");
  const modalAddFolder = document.getElementById("modal-add-folder");
  const btnCloseFolderModal = document.getElementById("btn-close-folder-modal");
  const btnCancelFolder = document.getElementById("btn-cancel-folder");
  const btnSaveFolder = document.getElementById("btn-save-folder");
  const inputFolderPath = document.getElementById("input-folder-path");
  const folderModalError = document.getElementById("folder-modal-error");
  const btnBrowseNative = document.getElementById("btn-browse-native");

  const btnOpenSettings = document.getElementById("btn-open-settings");
  const modalSettings = document.getElementById("modal-settings");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const btnTriggerRebuild = document.getElementById("btn-trigger-rebuild");
  const btnTriggerResume = document.getElementById("btn-trigger-resume");
  const settingsStatusMsg = document.getElementById("settings-status-msg");

  // Reader Modal
  const modalReader = document.getElementById("modal-reader");
  const btnCloseReader = document.getElementById("btn-close-reader");
  const readerFileIcon = document.getElementById("reader-file-icon");
  const readerFilename = document.getElementById("reader-filename");
  const readerMeta = document.getElementById("reader-meta");
  const readerContentText = document.getElementById("reader-content-text");
  const btnReaderOpen = document.getElementById("btn-reader-open");
  const btnReaderReveal = document.getElementById("btn-reader-reveal");
  const btnReaderCopy = document.getElementById("btn-reader-copy");

  // Realtime & Status Elements
  const syncBeacon = document.getElementById("sync-beacon");
  const syncBeaconText = document.getElementById("sync-beacon-text");
  const activityFeed = document.getElementById("activity-feed");
  const serviceStatus = document.getElementById("service-status");
  const statItemsCount = document.getElementById("stat-items-count");
  const statIndexed = document.getElementById("stat-indexed");
  const statChunks = document.getElementById("stat-chunks");
  const statQueue = document.getElementById("stat-queue");
  const statDb = document.getElementById("stat-db");
  const statSse = document.getElementById("stat-sse");
  const toast = document.getElementById("toast");

  // LLM DOM Elements
  const llmStatusBadge = document.getElementById("llm-status-badge");
  const llmStatusText = document.getElementById("llm-status-text");
  const modalLlm = document.getElementById("modal-llm");
  const btnCloseLlm = document.getElementById("btn-close-llm");
  const btnCloseLlmFooter = document.getElementById("btn-close-llm-footer");
  const llmDetailStatusPill = document.getElementById("llm-detail-status-pill");
  const llmProgressContainer = document.getElementById("llm-progress-container");
  const llmProgressBar = document.getElementById("llm-progress-bar");
  const llmProgressLabel = document.getElementById("llm-progress-label");
  const btnLlmActionDownload = document.getElementById("btn-llm-action-download");

  // Deep Qwen Synthesis Elements in Smart Answer
  const btnAskQwenAi = document.getElementById("btn-ask-qwen-ai");
  const qwenSynthesisBox = document.getElementById("qwen-synthesis-box");
  const qwenSynthesisText = document.getElementById("qwen-synthesis-text");
  const qwenMetaInfo = document.getElementById("qwen-meta-info");
  const qwenThinkingSteps = document.getElementById("qwen-thinking-steps");

  // Reader Modal AI Q&A Elements
  const readerAiInput = document.getElementById("reader-ai-input");
  const btnReaderAiAsk = document.getElementById("btn-reader-ai-ask");
  const readerAiResponse = document.getElementById("reader-ai-response");
  const readerAiText = document.getElementById("reader-ai-text");
  const readerThinkingSteps = document.getElementById("reader-thinking-steps");

  // Document Chat Panel Elements
  const modalDocChat = document.getElementById("modal-doc-chat");
  const btnOpenDocChat = document.getElementById("btn-open-doc-chat");
  const btnCloseDocChat = document.getElementById("btn-close-doc-chat");
  const docChatFileSelect = document.getElementById("doc-chat-file-select");
  const docChatSelectedInfo = document.getElementById("doc-chat-selected-info");
  const docChatMessages = document.getElementById("doc-chat-messages");
  const docChatInput = document.getElementById("doc-chat-input");
  const btnDocChatSend = document.getElementById("btn-doc-chat-send");

  // Mode state per context
  let currentModeMain = "balance";
  let currentModeReader = "balance";
  let currentModeDocChat = "balance";
  let docChatSelectedFileId = null;
  let docChatSelectedFileName = "";

  // -------------------------------------------------------------
  // Notification Toast Helper
  // -------------------------------------------------------------
  function showToast(message, duration = 3500) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove("hidden");
    setTimeout(() => {
      toast.classList.add("hidden");
    }, duration);
  }

  // -------------------------------------------------------------
  // Format & Typography Helpers
  // -------------------------------------------------------------
  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  function formatDate(isoStr) {
    if (!isoStr) return "-";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("id-ID", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch {
      return isoStr;
    }
  }

  function getFileIcon(ext) {
    const e = (ext || "").toLowerCase();
    if (e === ".pdf") return "📕";
    if (e === ".docx") return "📘";
    if (e === ".txt") return "📝";
    return "📄";
  }

  function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function highlightMatches(text, query) {
    if (!text || !query) return escapeHtml(text);
    const escapedText = escapeHtml(text);
    const terms = query
      .split(/\s+/)
      .map(t => t.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .filter(t => t.length > 2);
    
    if (terms.length === 0) return escapedText;

    const regex = new RegExp(`(${terms.join('|')})`, 'gi');
    return escapedText.replace(regex, '<mark>$1</mark>');
  }

  function getSelectedExtensions() {
    const exts = [];
    if (filterPdf.checked) exts.push(".pdf");
    if (filterDocx.checked) exts.push(".docx");
    if (filterTxt.checked) exts.push(".txt");
    return exts;
  }

  // -------------------------------------------------------------
  // 1-Click Pill Filters Behavior
  // -------------------------------------------------------------
  formatPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      formatPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      const filter = pill.dataset.filter;

      if (filter === "all") {
        filterPdf.checked = true;
        filterDocx.checked = true;
        filterTxt.checked = true;
      } else if (filter === ".pdf") {
        filterPdf.checked = true;
        filterDocx.checked = false;
        filterTxt.checked = false;
      } else if (filter === ".docx") {
        filterPdf.checked = false;
        filterDocx.checked = true;
        filterTxt.checked = false;
      } else if (filter === ".txt") {
        filterPdf.checked = false;
        filterDocx.checked = false;
        filterTxt.checked = true;
      }

      if (isSearching) {
        performSearch();
      } else {
        renderDefaultDashboard();
      }
    });
  });

  // Sort Pills
  if (sortRelevance && sortDate) {
    sortRelevance.addEventListener("click", () => {
      currentSort = "relevance";
      sortRelevance.classList.add("active");
      sortDate.classList.remove("active");
      if (isSearching && currentSearchResults.length > 0) {
        currentSearchResults.sort((a, b) => b.score - a.score);
        renderSearchCards(currentSearchResults, searchInput.value.trim());
      }
    });

    sortDate.addEventListener("click", () => {
      currentSort = "date";
      sortDate.classList.add("active");
      sortRelevance.classList.remove("active");
      if (isSearching && currentSearchResults.length > 0) {
        // Find matching file metadata for date
        currentSearchResults.sort((a, b) => {
          const fileA = allFiles.find(f => f.id === a.file_id);
          const fileB = allFiles.find(f => f.id === b.file_id);
          const timeA = fileA && fileA.modified_at ? new Date(fileA.modified_at).getTime() : 0;
          const timeB = fileB && fileB.modified_at ? new Date(fileB.modified_at).getTime() : 0;
          return timeB - timeA;
        });
        renderSearchCards(currentSearchResults, searchInput.value.trim());
      }
    });
  }

  // Topic Suggestion Chips
  if (topicChips) {
    topicChips.querySelectorAll(".chip-topic").forEach((chip) => {
      chip.addEventListener("click", () => {
        const query = chip.dataset.query;
        searchInput.value = query;
        btnClearSearch.style.display = "block";
        performSearch();
        window.scrollTo({ top: 380, behavior: "smooth" });
      });
    });
  }

  // -------------------------------------------------------------
  // Realtime SSE Connection (Automatic File Sync with Windows)
  // -------------------------------------------------------------
  function initEventSource() {
    if (sseSource) {
      sseSource.close();
    }

    try {
      sseSource = new EventSource("/api/files/stream");

      sseSource.addEventListener("connected", () => {
        statSse.classList.add("online");
        statSse.textContent = "● Realtime Sync Aktif";
        syncBeacon.classList.remove("syncing");
        syncBeaconText.textContent = "Realtime Watcher Aktif";
      });

      sseSource.addEventListener("file_detected", (e) => {
        try {
          const data = JSON.parse(e.data);
          flashSyncBeacon(`Mendeteksi: ${data.filename}...`);
        } catch {}
      });

      sseSource.addEventListener("file_indexed", (e) => {
        try {
          const data = JSON.parse(e.data);
          showToast(`📥 Berhasil diindeks: ${data.filename}`);
          flashSyncBeacon(`Selesai diindeks: ${data.filename}`);
          loadFiles();
          fetchStatus();
        } catch {}
      });

      sseSource.addEventListener("file_deleted", (e) => {
        try {
          const data = JSON.parse(e.data);
          showToast(`🗑️ Dihapus: ${data.filename}`);
          loadFiles();
          fetchStatus();
        } catch {}
      });

      sseSource.addEventListener("file_renamed", () => {
        loadFiles();
      });

      sseSource.onerror = () => {
        statSse.classList.remove("online");
        statSse.textContent = "○ Mencoba Menyambung...";
        syncBeaconText.textContent = "Mencoba Menghubungkan...";
      };
    } catch (err) {
      console.warn("SSE init failed:", err);
    }
  }

  function flashSyncBeacon(msg) {
    if (!syncBeacon) return;
    syncBeacon.classList.add("syncing");
    syncBeaconText.textContent = msg;
    setTimeout(() => {
      syncBeacon.classList.remove("syncing");
      syncBeaconText.textContent = "Realtime Watcher Aktif";
    }, 3500);
  }

  // -------------------------------------------------------------
  // Core Search Execution (Hybrid Semantic + BM25 + RRF)
  // -------------------------------------------------------------
  async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) {
      returnToDashboard();
      return;
    }

    if (activeSummaryAbortController) {
      activeSummaryAbortController.abort();
      activeSummaryAbortController = null;
    }

    isSearching = true;
    currentSynthesizedText = "";
    resultsBar.classList.remove("hidden");
    resultsCount.textContent = "Mencari konteks & kata kunci...";
    resultsLatency.textContent = "Menghitung...";
    smartAnswerBox.classList.add("hidden");
    if (resultsDividerLabel) resultsDividerLabel.classList.add("hidden");

    explorerViewContainer.innerHTML = `
      <div class="empty-hint" style="padding: 40px;">
        <div style="font-size: 28px; margin-bottom: 12px; animation: spin 1s infinite linear;">⚡</div>
        <div>Menjalankan Hybrid Retrieval (BM25 + Semantic Vector Cosine)...</div>
      </div>
    `;

    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          top_k: 12,
          extensions: getSelectedExtensions()
        })
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      currentSearchResults = data.results || [];

      renderSearchResultsView(data);
    } catch (err) {
      resultsCount.textContent = "Terjadi kesalahan saat mencari.";
      resultsLatency.textContent = "";
      if (resultsDividerLabel) resultsDividerLabel.classList.add("hidden");
      explorerViewContainer.innerHTML = `<div class="empty-hint" style="color: #fb7185; padding: 20px;">Error: ${err.message}</div>`;
    }
  }

  function renderSearchResultsView(data) {
    const { results, took_ms, query } = data;
    resultsLatency.textContent = `⚡ ${took_ms} ms (Lokal)`;

    if (!results || results.length === 0) {
      resultsCount.textContent = `Tidak ditemukan hasil untuk "${query}"`;
      smartAnswerBox.classList.add("hidden");
      if (resultsDividerLabel) resultsDividerLabel.classList.add("hidden");
      explorerViewContainer.innerHTML = `
        <div class="empty-hint" style="padding: 50px;">
          <div style="font-size: 32px; margin-bottom: 12px;">🔍</div>
          <h3 style="color: var(--text-primary); margin-bottom: 6px;">Tidak ada dokumen yang cocok</h3>
          <p style="color: var(--text-muted); font-size: 14px;">Coba gunakan sinonim, konsep lain, atau periksa filter ekstensi di atas.</p>
        </div>
      `;
      return;
    }

    resultsCount.textContent = `Ditemukan ${results.length} dokumen paling relevan:`;

    // 1. Featured Smart Answer Card (Top 1 Insight & Perplexity Sources)
    const topResult = results[0];
    lastSearchQuery = query;
    currentTopResults = results;

    if (topResult && topResult.snippet) {
      const relPct = Math.round(topResult.score * 100);
      currentSmartFileId = topResult.file_id;
      currentSmartText = topResult.snippet;

      smartAnswerBox.classList.remove("hidden");
      if (smartAnswerRelevance) smartAnswerRelevance.textContent = `${relPct}% Relevansi Semantik (${topResult.match_type.toUpperCase()})`;
      if (smartAnswerQuote) smartAnswerQuote.innerHTML = highlightMatches(topResult.snippet, query);
      if (smartSourceTitle) smartSourceTitle.textContent = topResult.filename;
      if (smartSourcePage) smartSourcePage.textContent = topResult.page_no ? `Hal. ${topResult.page_no}` : "Teks Utama";

      // Render Perplexity Sources Pills
      renderPerplexitySources(results.slice(0, 5));

      // Trigger Perplexity AI Conclusion if enabled
      if (isAutoSummaryEnabled) {
        generatePerplexitySummary(query, results);
      } else {
        if (btnAskQwenAi) btnAskQwenAi.classList.remove("hidden");
        if (qwenSynthesisText) {
          qwenSynthesisText.innerHTML = `
            <div class="synthesis-hint-empty">
              Auto Kesimpulan dinonaktifkan. Klik tombol <strong>✨ Buat Kesimpulan AI</strong> di bawah untuk merangkum dokumen temuan ini secara otomatis.
            </div>
          `;
        }
        if (qwenMetaInfo) qwenMetaInfo.textContent = "Mode Manual • Siap";
      }
    } else {
      smartAnswerBox.classList.add("hidden");
    }

    // 2. Show divider heading
    if (resultsDividerLabel) resultsDividerLabel.classList.remove("hidden");

    // 3. Render List of Knowledge Cards
    renderSearchCards(results, query);
  }

  function renderSearchCards(results, query) {
    let html = `<div class="search-results-list">`;

    results.forEach((item, idx) => {
      const relPct = Math.round(item.score * 100);
      const highlightedSnippet = highlightMatches(item.snippet, query);
      const sourceNum = idx < 5 ? idx + 1 : null;

      html += `
        <div class="search-result-card" data-file-id="${item.file_id}" data-source-index="${sourceNum || ''}">
          <div class="card-top-row">
            <div class="card-file-info">
              ${sourceNum ? `<span class="source-chip-num" title="Dokumen Rujukan [${sourceNum}]">[${sourceNum}]</span>` : ""}
              <span class="card-file-icon">${getFileIcon(item.extension)}</span>
              <span class="card-file-title" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</span>
            </div>
            <div class="card-badges">
              <span class="badge-relevance">Relevansi ${relPct}%</span>
              ${item.page_no ? `<span class="badge-page">Hal. ${item.page_no}</span>` : ""}
              <span class="badge-match">${item.match_type}</span>
            </div>
          </div>
          
          <div class="card-path" title="${escapeHtml(item.path)}">${escapeHtml(item.path)}</div>
          
          <div class="card-snippet">
            ${highlightedSnippet || "(Cuplikan teks tidak tersedia)"}
          </div>

          <div class="card-actions-row">
            <div class="card-meta-chips">
              <span>${item.extension.toUpperCase()}</span>
            </div>
            <div class="card-action-btns">
              <button class="btn-action-primary btn-open-act" data-file-id="${item.file_id}" title="Buka dengan aplikasi default Windows">
                📂 Buka File
              </button>
              <button class="btn-action-secondary btn-reader-act" data-file-id="${item.file_id}" title="Baca teks lengkap dokumen di web ini">
                👁️ Baca Dokumen
              </button>
              <button class="btn-action-secondary btn-reveal-act" data-file-id="${item.file_id}" title="Lihat letak file di Windows Explorer">
                🔍 Folder
              </button>
              <button class="btn-action-secondary btn-copy-snippet-act" data-text="${escapeHtml(item.snippet)}" title="Salin cuplikan teks">
                📋 Salin
              </button>
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    explorerViewContainer.innerHTML = html;
    attachResultCardEvents();
  }

  function attachResultCardEvents() {
    explorerViewContainer.querySelectorAll(".btn-open-act").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        handleOpenFile(parseInt(btn.dataset.fileId, 10));
      });
    });

    explorerViewContainer.querySelectorAll(".btn-reveal-act").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        handleRevealFile(parseInt(btn.dataset.fileId, 10));
      });
    });

    explorerViewContainer.querySelectorAll(".btn-reader-act").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openReaderModal(parseInt(btn.dataset.fileId, 10));
      });
    });

    explorerViewContainer.querySelectorAll(".btn-copy-snippet-act").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const text = btn.dataset.text;
        navigator.clipboard.writeText(text).then(() => {
          showToast("📋 Cuplikan teks berhasil disalin ke clipboard!");
        });
      });
    });

    explorerViewContainer.querySelectorAll(".search-result-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        const fileId = parseInt(card.dataset.fileId, 10);
        openReaderModal(fileId);
      });
    });
  }

  // -------------------------------------------------------------
  // Smart Answer Card Actions (Legacy & Safe Guards)
  // -------------------------------------------------------------
  if (btnSmartOpen) {
    btnSmartOpen.addEventListener("click", () => {
      if (currentSmartFileId) handleOpenFile(currentSmartFileId);
    });
  }

  if (btnSmartReveal) {
    btnSmartReveal.addEventListener("click", () => {
      if (currentSmartFileId) handleRevealFile(currentSmartFileId);
    });
  }

  if (btnSmartCopy) {
    btnSmartCopy.addEventListener("click", () => {
      if (currentSmartText) {
        navigator.clipboard.writeText(currentSmartText).then(() => {
          showToast("📋 Kutipan jawaban berhasil disalin ke clipboard!");
        });
      }
    });
  }

  // -------------------------------------------------------------
  // Default Knowledge Dashboard (When not searching)
  // -------------------------------------------------------------
  function returnToDashboard() {
    if (activeSummaryAbortController) {
      activeSummaryAbortController.abort();
      activeSummaryAbortController = null;
    }
    isSearching = false;
    searchInput.value = "";
    btnClearSearch.style.display = "none";
    resultsBar.classList.add("hidden");
    smartAnswerBox.classList.add("hidden");
    if (resultsDividerLabel) resultsDividerLabel.classList.add("hidden");
    if (qwenSynthesisBox) qwenSynthesisBox.classList.add("hidden");
    currentSynthesizedText = "";
    renderDefaultDashboard();
  }

  btnBackDashboard.addEventListener("click", returnToDashboard);

  function renderDefaultDashboard() {
    let allowedExts = getSelectedExtensions();
    let displayFiles = allFiles;
    if (allowedExts.length < 3) {
      displayFiles = displayFiles.filter(f => allowedExts.includes(f.extension.toLowerCase()));
    }

    statItemsCount.textContent = `${allFiles.length} dokumen`;

    let html = `
      <div class="dashboard-grid">
        <!-- 4 Metric Cards -->
        <div class="metrics-row">
          <div class="metric-card">
            <div class="metric-icon-box icon-blue">📚</div>
            <div class="metric-content">
              <span class="metric-value">${allFiles.length} Berkas</span>
              <span class="metric-label">Dokumen Lokal Terindeks</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon-box icon-indigo">🧩</div>
            <div class="metric-content">
              <span class="metric-value" id="dash-chunks-count">${statChunks.textContent || "0 chunks"}</span>
              <span class="metric-label">Potongan Vektor Semantik</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon-box icon-emerald">🛡️</div>
            <div class="metric-content">
              <span class="metric-value">$0 / Bulan</span>
              <span class="metric-label">100% Offline & Tanpa Cloud</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon-box icon-violet">⚡</div>
            <div class="metric-content">
              <span class="metric-value">&lt; 15 ms</span>
              <span class="metric-label">Latensi Hybrid RRF</span>
            </div>
          </div>
        </div>

        <!-- Two Columns Layout -->
        <div class="dashboard-two-col">
          <!-- Left: Recent Indexed Documents -->
          <div class="dash-panel">
            <div class="panel-header">
              <div>
                <h3 class="panel-title">Dokumen Siap Dicari</h3>
                <span class="panel-subtitle">Klik untuk membaca langsung atau buka file</span>
              </div>
              <span class="badge-zero-cost">${displayFiles.length} item</span>
            </div>

            <div class="recent-docs-list">
    `;

    if (displayFiles.length === 0) {
      html += `
        <div class="empty-hint" style="padding: 30px;">
          Belum ada dokumen yang sesuai filter ekstensi.
        </div>
      `;
    } else {
      displayFiles.slice(0, 15).forEach((file) => {
        html += `
          <div class="recent-doc-item" data-file-id="${file.id}">
            <div class="doc-info-left">
              <span style="font-size: 20px;">${getFileIcon(file.extension)}</span>
              <div class="doc-name-group">
                <span class="doc-title-text" title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</span>
                <span class="doc-meta-text">${formatBytes(file.size_bytes)} • Diubah ${formatDate(file.modified_at)}</span>
              </div>
            </div>
            <div class="doc-actions-right">
              <button class="btn-action-secondary btn-reader-act" data-file-id="${file.id}" title="Baca Dokumen">👁️ Baca</button>
              <button class="btn-action-primary btn-open-act" data-file-id="${file.id}" title="Buka File di Windows">📂 Buka</button>
            </div>
          </div>
        `;
      });
    }

    html += `
            </div>
          </div>

          <!-- Right: Monitored Folders & Ingestion Status -->
          <div class="dash-panel">
            <div class="panel-header">
              <div>
                <h3 class="panel-title">Folder Pantauan</h3>
                <span class="panel-subtitle">Dipantau secara real-time</span>
              </div>
              <button class="btn-text-action" id="btn-quick-add-folder">+ Tambah</button>
            </div>

            <div class="folders-badge-list">
    `;

    if (foldersData.length === 0) {
      html += `<div class="empty-hint">Memuat folder...</div>`;
    } else {
      foldersData.forEach((f) => {
        html += `
          <div class="folder-chip-item">
            <div class="folder-chip-name" title="${escapeHtml(f.path)}">📁 ${escapeHtml(f.name)}</div>
            <span class="folder-chip-status">Aktif</span>
          </div>
        `;
      });
    }

    html += `
            </div>

            <div style="margin-top: 10px; padding-top: 14px; border-top: 1px solid var(--border-subtle);">
              <h4 style="font-size: 13px; font-weight: 600; margin-bottom: 6px; color: var(--text-primary);">Pintasan Navigasi:</h4>
              <p style="font-size: 12px; color: var(--text-muted); line-height: 1.5;">
                Gunakan <kbd class="kbd-hint">Ctrl + K</kbd> untuk langsung fokus ke kotak pencarian dari mana saja.
              </p>
            </div>
          </div>
        </div>
      </div>
    `;

    explorerViewContainer.innerHTML = html;
    attachResultCardEvents();

    const quickAdd = document.getElementById("btn-quick-add-folder");
    if (quickAdd) {
      quickAdd.addEventListener("click", () => {
        modalAddFolder.classList.remove("hidden");
      });
    }
  }

  // -------------------------------------------------------------
  // Data Loading: Files & Folders
  // -------------------------------------------------------------
  async function loadFiles() {
    try {
      const res = await fetch("/api/files?page=1&page_size=100");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      allFiles = data.items || [];
      if (!isSearching) {
        renderDefaultDashboard();
      }
    } catch (err) {
      console.error("Gagal memuat berkas:", err);
    }
  }

  async function loadFolders() {
    try {
      const res = await fetch("/api/folders");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      foldersData = await res.json();
      if (!isSearching) {
        renderDefaultDashboard();
      }
    } catch (err) {
      console.error("Gagal memuat folder:", err);
    }
  }

  // -------------------------------------------------------------
  // Quick Reader Modal (Pratinjau Isi Dokumen Tanpa Buka Word/PDF)
  // -------------------------------------------------------------
  async function openReaderModal(fileId) {
    activeReaderFileId = fileId;
    modalReader.classList.remove("hidden");
    readerContentText.textContent = "Memuat ekstrak teks dokumen...";

    try {
      const res = await fetch(`/api/files/${fileId}/preview`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      readerFileIcon.textContent = getFileIcon(data.extension);
      readerFilename.textContent = data.filename;
      readerMeta.textContent = `${data.extension.toUpperCase()} • ${formatBytes(data.size_bytes)} • ${data.chunk_count} Chunks Semantik`;
      readerContentText.textContent = data.preview_text || "(Dokumen tidak berisi teks yang dapat diekstrak)";

      // Reset AI section
      if (readerAiInput) readerAiInput.value = "";
      if (readerAiResponse) readerAiResponse.classList.add("hidden");
      if (readerAiText) readerAiText.textContent = "";
    } catch (err) {
      readerContentText.textContent = `Gagal memuat teks: ${err.message}`;
    }
  }

  btnCloseReader.addEventListener("click", () => {
    modalReader.classList.add("hidden");
  });

  modalReader.addEventListener("click", (e) => {
    if (e.target === modalReader) modalReader.classList.add("hidden");
  });

  btnReaderOpen.addEventListener("click", () => {
    if (activeReaderFileId) handleOpenFile(activeReaderFileId);
  });

  btnReaderReveal.addEventListener("click", () => {
    if (activeReaderFileId) handleRevealFile(activeReaderFileId);
  });

  btnReaderCopy.addEventListener("click", () => {
    const text = readerContentText.textContent;
    if (text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast("📋 Seluruh teks dokumen berhasil disalin ke clipboard!");
      });
    }
  });

  // -------------------------------------------------------------
  // Desktop Native OS Actions (Safe verified file_id)
  // -------------------------------------------------------------
  async function handleOpenFile(fileId) {
    showToast("⏳ Sedang membuka aplikasi Windows...", 2000);
    try {
      const res = await fetch(`/api/files/${fileId}/open`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal membuka file.");
      showToast(`📂 Berhasil dibuka: ${data.message}`);
    } catch (err) {
      showToast(`Error: ${err.message}`, 4000);
    }
  }

  async function handleRevealFile(fileId) {
    showToast("⏳ Membuka Windows Explorer...", 2000);
    try {
      const res = await fetch(`/api/files/${fileId}/reveal`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal menampilkan file.");
      showToast(`🔍 Folder dibuka di Windows Explorer: ${data.message}`);
    } catch (err) {
      showToast(`Error: ${err.message}`, 4000);
    }
  }

  // -------------------------------------------------------------
  // Search Input Events
  // -------------------------------------------------------------
  btnSubmitSearch.addEventListener("click", performSearch);

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      performSearch();
    } else if (e.key === "Escape") {
      returnToDashboard();
    }
  });

  searchInput.addEventListener("input", () => {
    if (searchInput.value.trim().length > 0) {
      btnClearSearch.style.display = "block";
    } else {
      btnClearSearch.style.display = "none";
      if (isSearching) returnToDashboard();
    }
  });

  btnClearSearch.addEventListener("click", returnToDashboard);

  // Global Keyboard Shortcut: Ctrl + K focuses search bar
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });

  // -------------------------------------------------------------
  // Status & Health Check
  // -------------------------------------------------------------
  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const data = await res.json();

      statIndexed.textContent = `Indexed: ${data.indexed_files} files`;
      statChunks.textContent = `${data.chunks} chunks vektor`;
      statQueue.textContent = `Antrean: ${data.queue_size}`;
      statDb.textContent = `Database: ${data.database_mode === "postgres" ? "PostgreSQL" : "SQLite Fallback (Aktif)"}`;

      serviceStatus.innerHTML = `
        <span class="dot" style="background-color: ${data.status === 'ok' ? '#10b981' : '#f43f5e'}"></span>
        <span class="status-text">${data.status === 'ok' ? 'Backend Siap' : 'Degraded'}</span>
      `;

      const dashChunks = document.getElementById("dash-chunks-count");
      if (dashChunks) {
        dashChunks.textContent = `${data.chunks} Chunks`;
      }
    } catch {
      serviceStatus.innerHTML = `
        <span class="dot" style="background-color: #fb7185"></span>
        <span class="status-text">Terputus</span>
      `;
    }
  }

  // -------------------------------------------------------------
  // Add Folder Modal Handlers
  // -------------------------------------------------------------
  btnAddFolderModal.addEventListener("click", () => {
    modalAddFolder.classList.remove("hidden");
    inputFolderPath.value = "";
    folderModalError.classList.add("hidden");
    inputFolderPath.focus();
  });

  btnCloseFolderModal.addEventListener("click", () => {
    modalAddFolder.classList.add("hidden");
  });

  btnCancelFolder.addEventListener("click", () => {
    modalAddFolder.classList.add("hidden");
  });

  if (btnBrowseNative) {
    btnBrowseNative.addEventListener("click", async () => {
      btnBrowseNative.disabled = true;
      const originalContent = btnBrowseNative.innerHTML;
      btnBrowseNative.innerHTML = `<span>Membuka Dialog Windows...</span>`;
      try {
        const res = await fetch("/api/folders/browse", { method: "POST" });
        const data = await res.json();
        if (data.status === "ok" && data.path) {
          inputFolderPath.value = data.path;
          folderModalError.classList.add("hidden");
        }
      } catch (err) {
        folderModalError.textContent = `Gagal membuka dialog: ${err.message}`;
        folderModalError.classList.remove("hidden");
      } finally {
        btnBrowseNative.disabled = false;
        btnBrowseNative.innerHTML = originalContent;
      }
    });
  }

  document.querySelectorAll(".btn-shortcut").forEach((btn) => {
    btn.addEventListener("click", () => {
      const folderKey = btn.dataset.path;
      inputFolderPath.value = folderKey;
      folderModalError.classList.add("hidden");
    });
  });

  btnSaveFolder.addEventListener("click", async () => {
    const rawPath = inputFolderPath.value.trim();
    if (!rawPath) {
      folderModalError.textContent = "Silakan masukkan atau pilih path folder.";
      folderModalError.classList.remove("hidden");
      return;
    }

    btnSaveFolder.disabled = true;
    btnSaveFolder.textContent = "Menyimpan & Memindai...";
    folderModalError.classList.add("hidden");

    try {
      const res = await fetch("/api/folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: rawPath })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal menambahkan folder.");

      showToast(`📁 Memantau: ${data.name}`);
      modalAddFolder.classList.add("hidden");
      loadFolders();
      loadFiles();
      fetchStatus();
    } catch (err) {
      folderModalError.textContent = err.message;
      folderModalError.classList.remove("hidden");
    } finally {
      btnSaveFolder.disabled = false;
      btnSaveFolder.textContent = "Mulai Pantau Folder Ini";
    }
  });

  // -------------------------------------------------------------
  // Settings Modal Handlers
  // -------------------------------------------------------------
  btnOpenSettings.addEventListener("click", () => {
    modalSettings.classList.remove("hidden");
    settingsStatusMsg.classList.add("hidden");
  });

  btnCloseSettings.addEventListener("click", () => {
    modalSettings.classList.add("hidden");
  });

  btnTriggerRebuild.addEventListener("click", async () => {
    if (!confirm("Rebuild akan membersihkan seluruh indeks dan membaca ulang dokumen. Lanjutkan?")) return;
    btnTriggerRebuild.disabled = true;
    settingsStatusMsg.textContent = "Memulai rebuild indeks dokumen...";
    settingsStatusMsg.classList.remove("hidden");

    try {
      const res = await fetch("/api/index/rebuild", { method: "POST" });
      const data = await res.json();
      settingsStatusMsg.textContent = `✓ Sukses: ${data.message || 'Rebuild dijadwalkan di latar belakang'}`;
      showToast("🔄 Rebuild indeks dimulai di background");
      setTimeout(() => {
        loadFiles();
        fetchStatus();
      }, 2000);
    } catch (err) {
      settingsStatusMsg.textContent = `Error: ${err.message}`;
    } finally {
      btnTriggerRebuild.disabled = false;
    }
  });

  btnTriggerResume.addEventListener("click", async () => {
    btnTriggerResume.disabled = true;
    settingsStatusMsg.textContent = "Menjadwalkan pemrosesan ulang pekerjaan gagal...";
    settingsStatusMsg.classList.remove("hidden");

    try {
      const res = await fetch("/api/index/resume", { method: "POST" });
      const data = await res.json();
      settingsStatusMsg.textContent = `✓ Sukses: ${data.message}`;
      showToast("▶️ Melanjutkan antrean pemrosesan");
    } catch (err) {
      settingsStatusMsg.textContent = `Error: ${err.message}`;
    } finally {
      btnTriggerResume.disabled = false;
    }
  });

  // -------------------------------------------------------------
  // MULTI-STEP THINKING ANIMATION ENGINE
  // -------------------------------------------------------------
  function runThinkingAnimation(stepsContainer, onComplete) {
    if (!stepsContainer) { onComplete?.(); return; }
    stepsContainer.classList.remove("hidden");
    const steps = stepsContainer.querySelectorAll(".thinking-step");
    steps.forEach(s => { s.classList.remove("active", "completed"); });

    let currentStep = 0;
    const stepTimings = [1500, 0, 0]; // Step 1 auto-completes; steps 2-3 controlled by caller

    function activateStep(idx) {
      if (idx >= steps.length) return;
      steps[idx].classList.add("active");
      steps[idx].classList.remove("completed");
    }

    function completeStep(idx) {
      if (idx >= steps.length) return;
      steps[idx].classList.remove("active");
      steps[idx].classList.add("completed");
    }

    // Step 1: "Mencari konteks..." — auto completes after 1.5s
    activateStep(0);
    setTimeout(() => {
      completeStep(0);
      // Step 2: "Qwen sedang berpikir..." — stays active until response
      activateStep(1);
    }, stepTimings[0]);

    return {
      // Called when API response starts arriving
      onResponseStart() {
        completeStep(1);
        activateStep(2);
      },
      // Called when response fully rendered
      onResponseDone() {
        completeStep(2);
        setTimeout(() => {
          stepsContainer.classList.add("hidden");
        }, 1200);
        onComplete?.();
      },
      // Called on error
      onError() {
        steps.forEach(s => { s.classList.remove("active"); });
        stepsContainer.classList.add("hidden");
        onComplete?.();
      }
    };
  }

  // Inline thinking for chat bubbles (Document Chat)
  function createChatThinkingHTML() {
    return `
      <div class="chat-thinking-steps">
        <div class="chat-thinking-item active" data-step="1">
          <span class="step-spinner"></span>
          <span>🔍 Mencari konteks di dokumen...</span>
        </div>
        <div class="chat-thinking-item" data-step="2">
          <span class="step-spinner"></span>
          <span>🧠 Qwen sedang berpikir...</span>
        </div>
        <div class="chat-thinking-item" data-step="3">
          <span class="step-spinner"></span>
          <span>✍️ Menyusun jawaban...</span>
        </div>
      </div>
    `;
  }

  function runChatBubbleThinking(bubbleEl) {
    const items = bubbleEl.querySelectorAll(".chat-thinking-item");
    if (!items.length) return { onResponseStart(){}, onResponseDone(){}, onError(){} };

    // Step 1 active initially
    setTimeout(() => {
      items[0].classList.remove("active");
      items[0].classList.add("completed");
      items[1].classList.add("active");
    }, 1500);

    return {
      onResponseStart() {
        items[1].classList.remove("active");
        items[1].classList.add("completed");
        items[2].classList.add("active");
      },
      onResponseDone() {
        items[2].classList.remove("active");
        items[2].classList.add("completed");
      },
      onError() {
        items.forEach(i => i.classList.remove("active"));
      }
    };
  }

  // -------------------------------------------------------------
  // MODE SELECTOR PILL LOGIC
  // -------------------------------------------------------------
  function initModeSelector(containerId, onModeChange) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.querySelectorAll(".mode-pill").forEach(pill => {
      pill.addEventListener("click", () => {
        container.querySelectorAll(".mode-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        onModeChange(pill.dataset.mode);
      });
    });
  }

  initModeSelector("mode-selector-main", (mode) => {
    currentModeMain = mode;
    if (isSearching && currentTopResults && currentTopResults.length > 0) {
      generatePerplexitySummary(lastSearchQuery, currentTopResults);
    }
  });
  initModeSelector("mode-selector-reader", (mode) => { currentModeReader = mode; });
  initModeSelector("mode-selector-doc-chat", (mode) => { currentModeDocChat = mode; });

  // -------------------------------------------------------------
  // QWEN 2.5 LOCAL AI & CHAT INTERACTION
  // -------------------------------------------------------------
  // QWEN LOCAL AI & MULTI-MODEL MANAGER
  // -------------------------------------------------------------
  let llmPollingInterval = null;
  const llmModelsCatalog = document.getElementById("llm-models-catalog");
  const llmDownloadCard = document.getElementById("llm-download-card");
  const llmDownloadTitle = document.getElementById("llm-download-title");

  async function checkLLMStatus() {
    try {
      const res = await fetch("/api/llm/status");
      if (!res.ok) return;
      const data = await res.json();

      // Update Navbar Badge
      if (llmStatusBadge && llmStatusText) {
        if (data.model_exists) {
          llmStatusBadge.className = "badge-pill badge-llm status-ready";
          const shortName = (data.model_name && data.model_name.includes("0.5b"))
            ? "Qwen 0.5B: Aktif (⚡ 468MB)"
            : "Qwen 1.5B: Aktif (🧠 1.06GB)";
          llmStatusText.textContent = shortName;
        } else if (data.is_downloading) {
          const pct = data.download_progress_pct || 0;
          llmStatusBadge.className = "badge-pill badge-llm status-downloading";
          llmStatusText.textContent = `Unduh Model: ${pct}%`;
        } else {
          llmStatusBadge.className = "badge-pill badge-llm status-missing";
          llmStatusText.textContent = "⚡ Pilih Model AI";
        }
      }

      // Update Perplexity Card Header Badge
      const perplexityModelBadge = document.getElementById("perplexity-active-model-badge");
      if (data.model_name && data.model_name.includes("0.5b")) {
        currentActiveModelDisplayName = "⚡ Qwen 2.5 0.5B (468 MB)";
      } else {
        currentActiveModelDisplayName = "🧠 Qwen 2.5 1.5B (1.06 GB)";
      }
      if (perplexityModelBadge) {
        if (data.model_name && data.model_name.includes("0.5b")) {
          perplexityModelBadge.textContent = "⚡ Qwen 2.5 0.5B (468 MB) • Offline";
          perplexityModelBadge.style.color = "#38bdf8";
          perplexityModelBadge.style.borderColor = "rgba(56, 189, 248, 0.4)";
          perplexityModelBadge.style.background = "rgba(56, 189, 248, 0.12)";
        } else {
          perplexityModelBadge.textContent = "🧠 Qwen 2.5 1.5B (1.06 GB) • Offline";
          perplexityModelBadge.style.color = "#c084fc";
          perplexityModelBadge.style.borderColor = "rgba(192, 132, 252, 0.4)";
          perplexityModelBadge.style.background = "rgba(192, 132, 252, 0.12)";
        }
      }

      // Render Model Catalog in Modal
      if (llmModelsCatalog && data.available_models) {
        renderModelCatalog(data.available_models, data.model_name);
      }

      // Progress bar if downloading
      if (llmDownloadCard) {
        if (data.is_downloading) {
          llmDownloadCard.classList.remove("hidden");
          const pct = data.download_progress_pct || 0;
          if (llmProgressBar) llmProgressBar.style.width = `${pct}%`;
          if (llmProgressLabel) llmProgressLabel.textContent = `${pct}%`;
          if (llmDetailStatusPill) {
            llmDetailStatusPill.className = "badge-pill status-downloading";
            llmDetailStatusPill.textContent = `${pct}%`;
          }
          if (!llmPollingInterval) {
            llmPollingInterval = setInterval(checkLLMStatus, 2000);
          }
        } else {
          llmDownloadCard.classList.add("hidden");
          if (llmPollingInterval) {
            clearInterval(llmPollingInterval);
            llmPollingInterval = null;
          }
        }
      }
    } catch (err) {
      console.warn("Gagal mengecek status LLM:", err);
    }
  }

  function renderModelCatalog(models, activeModelName) {
    if (!llmModelsCatalog) return;
    let html = "";
    models.forEach(m => {
      const isActive = (m.filename === activeModelName);
      const isInstalled = m.is_installed;
      const tagClass = m.recommended ? "model-tag-pill rec" : "model-tag-pill";
      
      let actionBtn = "";
      if (isActive) {
        actionBtn = `<button class="btn-switch-model active" disabled>🟢 Aktif Digunakan</button>`;
      } else if (isInstalled) {
        actionBtn = `<button class="btn-switch-model btn-use-model" data-filename="${m.filename}">Gunakan Model Ini</button>`;
      } else {
        actionBtn = `<button class="btn-switch-model btn-primary btn-dl-model" data-filename="${m.filename}" data-repoid="${m.repo_id}">⚡ Unduh (~${m.size_mb} MB)</button>`;
      }

      html += `
        <div class="llm-model-card ${isActive ? 'active' : ''}">
          <div class="model-card-info">
            <div class="model-card-title-row">
              <span class="model-card-name">${escapeHtml(m.name)}</span>
              <span class="${tagClass}">${escapeHtml(m.tag)}</span>
              ${m.recommended ? '<span style="font-size: 11px; color: #34d399; font-weight: 600;">★ Rekomendasi SENA</span>' : ''}
            </div>
            <div class="model-card-desc">${escapeHtml(m.description)}</div>
            <div class="model-card-meta">Ukuran file: ${m.size_mb} MB • ${isInstalled ? '✓ Terpasang di laptop' : 'Belum diunduh'}</div>
          </div>
          <div class="model-card-actions">
            ${actionBtn}
          </div>
        </div>
      `;
    });
    llmModelsCatalog.innerHTML = html;

    // Attach switch clicks
    llmModelsCatalog.querySelectorAll(".btn-use-model").forEach(btn => {
      btn.addEventListener("click", async () => {
        const fn = btn.dataset.filename;
        btn.disabled = true;
        btn.textContent = "Beralih...";
        await switchModel(fn);
      });
    });

    // Attach download clicks
    llmModelsCatalog.querySelectorAll(".btn-dl-model").forEach(btn => {
      btn.addEventListener("click", async () => {
        const fn = btn.dataset.filename;
        btn.disabled = true;
        btn.textContent = "Mengunduh...";
        await triggerModelDownload(fn);
      });
    });
  }

  async function switchModel(modelFilename) {
    try {
      showToast(`🔄 Beralih ke model ${modelFilename}...`);
      const res = await fetch("/api/llm/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_name: modelFilename })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal beralih model.");
      showToast(`✅ Berhasil beralih ke: ${modelFilename}!`);
      checkLLMStatus();
    } catch (err) {
      showToast(`❌ Gagal ganti model: ${err.message}`);
      checkLLMStatus();
    }
  }

  async function triggerModelDownload(modelFilename) {
    try {
      showToast(`⏳ Memulai unduhan model ${modelFilename}...`);
      const res = await fetch("/api/llm/download", { method: "POST" });
      const data = await res.json();
      showToast("⏳ Unduhan model berjalan di latar belakang...");
      checkLLMStatus();
    } catch (err) {
      showToast(`Gagal memulai unduhan: ${err.message}`);
    }
  }

  // LLM Status Badge Click -> Open Model Manager Modal
  if (llmStatusBadge) {
    llmStatusBadge.addEventListener("click", () => {
      if (modalLlm) modalLlm.classList.remove("hidden");
      checkLLMStatus();
    });
  }

  if (btnCloseLlm) {
    btnCloseLlm.addEventListener("click", () => {
      modalLlm.classList.add("hidden");
    });
  }

  if (btnCloseLlmFooter) {
    btnCloseLlmFooter.addEventListener("click", () => {
      modalLlm.classList.add("hidden");
    });
  }

  // ---------------------------------------------------------------
  // PERPLEXITY-STYLE AI KESIMPULAN & SOURCES SYNTHESIS
  // ---------------------------------------------------------------

  // Toggle Auto-Summary switch listener
  if (toggleAutoSummary) {
    toggleAutoSummary.checked = isAutoSummaryEnabled;
    toggleAutoSummary.addEventListener("change", (e) => {
      isAutoSummaryEnabled = e.target.checked;
      localStorage.setItem("sena_auto_summary", isAutoSummaryEnabled ? "true" : "false");
      if (isAutoSummaryEnabled && isSearching && currentTopResults && currentTopResults.length > 0 && !currentSynthesizedText) {
        generatePerplexitySummary(lastSearchQuery, currentTopResults);
      }
    });
  }

  // Render Horizontal Sources Carousel Pills [1], [2], [3]
  function renderPerplexitySources(topResults) {
    if (!perplexitySourcesList) return;
    if (!topResults || topResults.length === 0) {
      perplexitySourcesList.innerHTML = `<span style="color: var(--text-muted); font-size: 12px;">Tidak ada dokumen rujukan</span>`;
      return;
    }

    let html = "";
    topResults.forEach((item, idx) => {
      const relPct = Math.round(item.score * 100);
      const citeIdx = idx + 1;
      html += `
        <div class="perplexity-source-chip" data-file-id="${item.file_id}" data-index="${citeIdx}" title="${escapeHtml(item.filename)} — Relevansi ${relPct}% (${item.match_type.toUpperCase()})">
          <span class="source-chip-num">[${citeIdx}]</span>
          <span class="card-file-icon">${getFileIcon(item.extension)}</span>
          <span class="source-chip-name">${escapeHtml(item.filename)}</span>
          <span class="source-chip-rel">${relPct}%</span>
        </div>
      `;
    });

    perplexitySourcesList.innerHTML = html;

    // Attach click events to source chips
    perplexitySourcesList.querySelectorAll(".perplexity-source-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const citeIdx = chip.dataset.index;
        const fileId = chip.dataset.fileId;
        const targetCard = explorerViewContainer.querySelector(`.search-result-card[data-source-index="${citeIdx}"]`);
        if (targetCard) {
          targetCard.scrollIntoView({ behavior: "smooth", block: "center" });
          targetCard.classList.remove("card-highlight-flash");
          void targetCard.offsetWidth;
          targetCard.classList.add("card-highlight-flash");
          showToast(`🎯 Menuju Dokumen [${citeIdx}] ${chip.querySelector(".source-chip-name").textContent}`);
        } else if (fileId) {
          openReaderModal(parseInt(fileId, 10));
        }
      });
    });
  }

  // Render AI Summary Markdown with Interactive Citation Badges
  function renderPerplexityMarkdown(text, sources) {
    if (!text) return "";

    let escaped = escapeHtml(text);

    // Citations [1], [2], etc. -> interactive badges
    escaped = escaped.replace(/\[(\d+)\]/g, (match, num) => {
      const idx = parseInt(num, 10);
      const source = sources && sources[idx - 1];
      const sourceTitle = source ? `${escapeHtml(source.filename)} (${Math.round((source.score || 0) * 100)}%)` : `Rujukan ${idx}`;
      return `<span class="citation-badge" data-cite-idx="${idx}" title="Rujukan [${idx}]: ${sourceTitle}">[${idx}]</span>`;
    });

    // Headers
    escaped = escaped.replace(/^###\s+(.*$)/gim, '<h4>$1</h4>');
    escaped = escaped.replace(/^##\s+(.*$)/gim, '<h4>$1</h4>');

    // Bold & Italic
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Lists and paragraphs
    const lines = escaped.split(/\r?\n/);
    let inList = false;
    let listType = "";
    let htmlOutput = "";

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();

      if (!line) {
        if (inList) {
          htmlOutput += `</${listType}>`;
          inList = false;
        }
        continue;
      }

      const bulletMatch = line.match(/^[-*]\s+(.*)$/);
      const numberMatch = line.match(/^(\d+)\.\s+(.*)$/);

      if (bulletMatch) {
        if (!inList || listType !== "ul") {
          if (inList) htmlOutput += `</${listType}>`;
          htmlOutput += "<ul>";
          inList = true;
          listType = "ul";
        }
        htmlOutput += `<li>${bulletMatch[1]}</li>`;
      } else if (numberMatch) {
        if (!inList || listType !== "ol") {
          if (inList) htmlOutput += `</${listType}>`;
          htmlOutput += "<ol>";
          inList = true;
          listType = "ol";
        }
        htmlOutput += `<li>${numberMatch[2]}</li>`;
      } else {
        if (inList) {
          htmlOutput += `</${listType}>`;
          inList = false;
        }
        if (line.startsWith("<h4>") && line.endsWith("</h4>")) {
          htmlOutput += line;
        } else {
          htmlOutput += `<p>${line}</p>`;
        }
      }
    }

    if (inList) {
      htmlOutput += `</${listType}>`;
    }

    return htmlOutput;
  }

  // Attach click listener for [1], [2] badges inside summary
  function attachCitationClicks() {
    if (!qwenSynthesisText) return;
    qwenSynthesisText.querySelectorAll(".citation-badge").forEach(badge => {
      badge.addEventListener("click", (e) => {
        e.stopPropagation();
        const citeIdx = badge.dataset.citeIdx;
        const targetCard = explorerViewContainer.querySelector(`.search-result-card[data-source-index="${citeIdx}"]`);
        if (targetCard) {
          targetCard.scrollIntoView({ behavior: "smooth", block: "center" });
          targetCard.classList.remove("card-highlight-flash");
          void targetCard.offsetWidth;
          targetCard.classList.add("card-highlight-flash");
          showToast(`🎯 Rujukan Dokumen [${citeIdx}]`);
        } else if (perplexitySourcesList) {
          const sourceChip = perplexitySourcesList.querySelector(`.perplexity-source-chip[data-index="${citeIdx}"]`);
          if (sourceChip) {
            const fileId = sourceChip.dataset.fileId;
            if (fileId) openReaderModal(parseInt(fileId, 10));
          }
        }
      });
    });
  }

  // Main Generator Function for Perplexity Summary
  async function generatePerplexitySummary(query, results) {
    if (!query || !results || results.length === 0) return;

    if (activeSummaryAbortController) {
      activeSummaryAbortController.abort();
    }
    activeSummaryAbortController = new AbortController();

    if (btnAskQwenAi) btnAskQwenAi.classList.add("hidden");
    if (btnCopySummary) btnCopySummary.disabled = true;
    if (btnRefreshSummary) btnRefreshSummary.disabled = true;

    // Reset view & show initial status
    if (qwenSynthesisText) {
      qwenSynthesisText.innerHTML = '<div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Sedang menganalisis dokumen...</div>';
    }
    if (qwenMetaInfo) {
      const modeLabels = { fast: "⚡ Cepat", balance: "⚖️ Balance", thinking: "🧠 Thinking" };
      qwenMetaInfo.textContent = `${currentActiveModelDisplayName} • ${modeLabels[currentModeMain] || "⚖️ Balance"} • Menghubungi model lokal...`;
    }

    const anim = runThinkingAnimation(qwenThinkingSteps);

    try {
      const res = await fetch("/api/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: activeSummaryAbortController.signal,
        body: JSON.stringify({
          query: query,
          top_k: 5,
          mode: currentModeMain
        })
      });

      anim.onResponseStart();

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal mendapatkan respon dari AI.");

      currentSynthesizedText = data.answer || "";
      if (qwenSynthesisText) {
        qwenSynthesisText.innerHTML = renderPerplexityMarkdown(currentSynthesizedText, results);
        attachCitationClicks();
      }

      if (qwenMetaInfo) {
        qwenMetaInfo.textContent = `${data.model || "Qwen 2.5"} • ${data.mode_label || "⚖️ Balance"} • ${data.duration_s || 0}s • ${data.tokens_used || 0} token`;
      }

      if (btnCopySummary) btnCopySummary.disabled = false;
      if (btnRefreshSummary) btnRefreshSummary.disabled = false;
      anim.onResponseDone();
    } catch (err) {
      if (err.name === "AbortError") {
        return; // Stale request cancelled by newer query
      }
      anim.onError();
      if (qwenSynthesisText) {
        qwenSynthesisText.innerHTML = `
          <div style="color: #fb7185; padding: 8px 0; font-size: 14px;">
            ⚠️ Kendala penyusunan kesimpulan: ${escapeHtml(err.message)}
          </div>
        `;
      }
      if (qwenMetaInfo) qwenMetaInfo.textContent = "Gagal memproses";
      if (btnAskQwenAi) btnAskQwenAi.classList.remove("hidden");
    } finally {
      if (btnRefreshSummary) btnRefreshSummary.disabled = false;
    }
  }

  // Header quick action listeners
  if (btnCopySummary) {
    btnCopySummary.addEventListener("click", () => {
      if (currentSynthesizedText) {
        navigator.clipboard.writeText(currentSynthesizedText).then(() => {
          showToast("📋 Kesimpulan AI berhasil disalin!");
        });
      } else {
        showToast("Belum ada kesimpulan untuk disalin.");
      }
    });
  }

  if (btnRefreshSummary) {
    btnRefreshSummary.addEventListener("click", () => {
      if (lastSearchQuery && currentTopResults && currentTopResults.length > 0) {
        showToast("🔄 Menyusun ulang kesimpulan...");
        generatePerplexitySummary(lastSearchQuery, currentTopResults);
      }
    });
  }

  if (btnToggleSummaryCollapse) {
    btnToggleSummaryCollapse.addEventListener("click", () => {
      if (perplexitySummaryBody) {
        perplexitySummaryBody.classList.toggle("collapsed");
        const isCollapsed = perplexitySummaryBody.classList.contains("collapsed");
        if (summaryCollapseIcon) {
          summaryCollapseIcon.textContent = isCollapsed ? "▼" : "▲";
        }
      }
    });
  }

  if (btnAskQwenAi) {
    btnAskQwenAi.addEventListener("click", () => {
      if (lastSearchQuery && currentTopResults && currentTopResults.length > 0) {
        generatePerplexitySummary(lastSearchQuery, currentTopResults);
      }
    });
  }

  // ---------------------------------------------------------------
  // Reader Modal AI Q&A (with Thinking + Mode)
  // ---------------------------------------------------------------
  async function askReaderAi() {
    if (!activeReaderFileId) return;
    const q = readerAiInput.value.trim() || "Rangkum dokumen ini secara ringkas, jelas, dan sebutkan poin-poin terpentingnya.";
    
    readerAiResponse.classList.remove("hidden");
    readerAiText.textContent = "";

    // Start thinking animation
    const anim = runThinkingAnimation(readerThinkingSteps);

    try {
      const res = await fetch("/api/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, file_id: activeReaderFileId, top_k: 4, mode: currentModeReader })
      });

      anim.onResponseStart();

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal mendapatkan respon AI.");

      readerAiText.textContent = data.answer;
      anim.onResponseDone();
    } catch (err) {
      anim.onError();
      readerAiText.textContent = `Kendala AI: ${err.message}`;
    }
  }

  if (btnReaderAiAsk) {
    btnReaderAiAsk.addEventListener("click", askReaderAi);
  }

  if (readerAiInput) {
    readerAiInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        askReaderAi();
      }
    });
  }

  // ---------------------------------------------------------------
  // DOCUMENT CHAT PANEL
  // ---------------------------------------------------------------

  // Open/Close Document Chat Modal
  if (btnOpenDocChat) {
    btnOpenDocChat.addEventListener("click", () => {
      modalDocChat.classList.remove("hidden");
      populateDocChatFileList();
    });
  }

  if (btnCloseDocChat) {
    btnCloseDocChat.addEventListener("click", () => {
      modalDocChat.classList.add("hidden");
    });
  }

  if (modalDocChat) {
    modalDocChat.addEventListener("click", (e) => {
      if (e.target === modalDocChat) modalDocChat.classList.add("hidden");
    });
  }

  // Populate file dropdown from indexed files
  function populateDocChatFileList() {
    if (!docChatFileSelect) return;
    const currentVal = docChatFileSelect.value;
    docChatFileSelect.innerHTML = '<option value="" disabled selected>— Pilih dokumen yang sudah diindeks —</option>';

    const indexedFiles = allFiles.filter(f => f.status === "INDEXED" || f.status === undefined);
    indexedFiles.forEach(f => {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.textContent = `${getFileIcon(f.extension)} ${f.filename} (${formatBytes(f.size_bytes)})`;
      docChatFileSelect.appendChild(opt);
    });

    // Restore selection if still valid
    if (currentVal && indexedFiles.some(f => String(f.id) === currentVal)) {
      docChatFileSelect.value = currentVal;
    }
  }

  // File selection handler
  if (docChatFileSelect) {
    docChatFileSelect.addEventListener("change", () => {
      const fileId = parseInt(docChatFileSelect.value, 10);
      if (!fileId) return;

      docChatSelectedFileId = fileId;
      const file = allFiles.find(f => f.id === fileId);
      docChatSelectedFileName = file ? file.filename : "Dokumen";

      docChatSelectedInfo.textContent = `✓ ${docChatSelectedFileName}`;
      docChatSelectedInfo.style.color = "#34d399";

      // Enable input
      docChatInput.disabled = false;
      docChatInput.placeholder = `Tanyakan tentang "${docChatSelectedFileName}"...`;
      btnDocChatSend.disabled = false;

      // Clear messages and show ready state
      docChatMessages.innerHTML = `
        <div class="doc-chat-placeholder">
          <div class="placeholder-icon">💬</div>
          <h4>Siap untuk chat tentang ${escapeHtml(docChatSelectedFileName)}</h4>
          <p>Ketik pertanyaan Anda di bawah. AI hanya akan menjawab berdasarkan isi dokumen ini.</p>
        </div>
      `;

      docChatInput.focus();
    });
  }

  // Send message in Document Chat
  async function sendDocChatMessage() {
    if (!docChatSelectedFileId) {
      showToast("⚠️ Pilih dokumen terlebih dahulu!");
      return;
    }

    const q = docChatInput.value.trim();
    if (!q) return;

    // Clear placeholder if first message
    const placeholder = docChatMessages.querySelector(".doc-chat-placeholder");
    if (placeholder) placeholder.remove();

    // Add user bubble
    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble user-bubble";
    userBubble.innerHTML = `
      <span class="chat-bubble-label">Anda</span>
      ${escapeHtml(q)}
    `;
    docChatMessages.appendChild(userBubble);

    // Clear input
    docChatInput.value = "";
    docChatInput.disabled = true;
    btnDocChatSend.disabled = true;

    // Add AI thinking bubble
    const aiBubble = document.createElement("div");
    aiBubble.className = "chat-bubble ai-bubble";
    aiBubble.innerHTML = `
      <span class="chat-bubble-label">🤖 Qwen 2.5 AI</span>
      ${createChatThinkingHTML()}
      <div class="chat-answer-text"></div>
    `;
    docChatMessages.appendChild(aiBubble);
    docChatMessages.scrollTop = docChatMessages.scrollHeight;

    // Start thinking animation in bubble
    const anim = runChatBubbleThinking(aiBubble);
    const answerEl = aiBubble.querySelector(".chat-answer-text");

    try {
      const res = await fetch("/api/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          file_id: docChatSelectedFileId,
          top_k: 4,
          mode: currentModeDocChat,
          doc_chat: true
        })
      });

      anim.onResponseStart();

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal mendapatkan respon AI.");

      anim.onResponseDone();

      // Remove thinking steps, show answer
      const thinkingEl = aiBubble.querySelector(".chat-thinking-steps");
      if (thinkingEl) {
        setTimeout(() => { thinkingEl.remove(); }, 600);
      }

      answerEl.textContent = data.answer;
      answerEl.innerHTML += `
        <div class="chat-bubble-meta">
          <span>${data.mode_label}</span>
          <span>•</span>
          <span>${data.duration_s}s</span>
          <span>•</span>
          <span>${data.tokens_used} tokens</span>
        </div>
      `;
    } catch (err) {
      anim.onError();
      const thinkingEl = aiBubble.querySelector(".chat-thinking-steps");
      if (thinkingEl) thinkingEl.remove();
      answerEl.textContent = `❌ ${err.message}`;
      answerEl.style.color = "#fb7185";
    }

    // Re-enable input
    docChatInput.disabled = false;
    btnDocChatSend.disabled = false;
    docChatInput.focus();
    docChatMessages.scrollTop = docChatMessages.scrollHeight;
  }

  if (btnDocChatSend) {
    btnDocChatSend.addEventListener("click", sendDocChatMessage);
  }

  if (docChatInput) {
    docChatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendDocChatMessage();
      }
    });
  }

  // -------------------------------------------------------------
  // Initial Boot Sequence
  // -------------------------------------------------------------
  initEventSource();
  loadFolders();
  loadFiles();
  fetchStatus();
  checkLLMStatus();
  setInterval(fetchStatus, 15000);
});
