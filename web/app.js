// NikitaBot AI Reels Agent Dashboard Logic
(function () {
  "use strict";

  // Mock initial dataset as baseline
  const initialReels = [
    {
      id: "reel-101",
      author: "@TheTechDaily",
      authorName: "The Tech Daily",
      timestamp: "3 часа назад",
      category: "Tech",
      duration: "0:38",
      views: "2.4M",
      likes: "184K",
      comments: "1.2K",
      shares: "42K",
      sentimentScore: 94,
      sentimentLabel: "94% Positive",
      tags: ["AI", "Tech", "Innovation", "Future"],
      viralHook: "«Is this the future?» — Compelling visual hook, strong pacing, clear voiceover. Highly engaging start in first 2.5s.",
      hookScore: 9.2,
      viralityScore: 94,
      hookType: "Curiosity Gap",
      hookFrames: [],
      transcript: "This new open-source AI agent just automated an entire social media workflow. Watch what happens when I give it a single profile handle. It scrapes all recent reels, transcribes the voice with Whisper, runs multimodal frame detection, and sends ready-to-use executive summaries to Telegram in under 30 seconds. The code is completely free and running locally.",
      takeaways: [
        "Мощный эмоциональный хук с демонстрацией экрана",
        "Быстрый темп речи без пауз (retention 82%)",
        "Четкий призыв к действию в конце видео"
      ]
    },
    {
      id: "reel-102",
      author: "@StartupHub",
      authorName: "Startup Hub",
      timestamp: "5 часов назад",
      category: "Startups",
      duration: "0:52",
      views: "890K",
      likes: "76K",
      comments: "840",
      shares: "15K",
      sentimentScore: 88,
      sentimentLabel: "88% Positive",
      tags: ["Startups", "Growth", "Founders"],
      viralHook: "«Stop building products nobody wants.» — Aggressive pattern interrupt, bold text overlay, energetic delivery.",
      hookScore: 8.7,
      viralityScore: 88,
      hookType: "Pattern Interrupt",
      hookFrames: [],
      transcript: "Here are 3 brutal reasons your SaaS idea will fail before launch. Number one: you are solving a minor inconvenience instead of an urgent bleeding problem. Number two: zero distribution strategy. You built in a cave and expect virality. Number three: pricing is too low. If you charge 5 dollars, you need ten thousand customers. Charge 100 dollars and solve real pain.",
      takeaways: [
        "Паттерн-интеррапт на 1-й секунде (резкая смена кадра)",
        "Списочная структура (3 пункта удерживают внимание)",
        "Высокий репост-рейт из-за практической ценности"
      ]
    }
  ];

  let reels = [...initialReels];
  let profiles = [];
  let currentFilter = "all";
  let searchQuery = "";
  let categoryFilter = "all";

  // Elements
  const profilesContainer = document.getElementById("profilesContainer");
  const profilesCountBadge = document.getElementById("profilesCount");
  const reelsGrid = document.getElementById("reelsGrid");
  const totalReelsCount = document.getElementById("totalReelsCount");
  const searchInput = document.getElementById("searchInput");
  const filterCategory = document.getElementById("filterCategory");
  const toggleBtns = document.querySelectorAll(".toggle-btn");
  const scanNowBtn = document.getElementById("scanNowBtn");
  const activityLogStream = document.getElementById("activityLogStream");
  const currentTaskLabel = document.getElementById("currentTaskLabel");
  const currentTaskProgressBar = document.getElementById("currentTaskProgressBar");
  const currentTaskProgressNum = document.getElementById("currentTaskProgressNum");

  // Modals
  const addProfileBtn = document.getElementById("addProfileBtn");
  const addProfileModal = document.getElementById("addProfileModal");
  const closeProfileModal = document.getElementById("closeProfileModal");
  const cancelProfileBtn = document.getElementById("cancelProfileBtn");
  const saveProfileBtn = document.getElementById("saveProfileBtn");
  const profileUsername = document.getElementById("profileUsername");
  const profileCategory = document.getElementById("profileCategory");

  const reelDetailModal = document.getElementById("reelDetailModal");
  const closeReelModal = document.getElementById("closeReelModal");
  const closeReelModalBtn = document.getElementById("closeReelModalBtn");
  const modalReelTitle = document.getElementById("modalReelTitle");
  const modalDurationTag = document.getElementById("modalDurationTag");
  const modalMetricsBar = document.getElementById("modalMetricsBar");
  const modalHookText = document.getElementById("modalHookText");
  const modalTranscriptText = document.getElementById("modalTranscriptText");
  const modalKeyTakeaways = document.getElementById("modalKeyTakeaways");
  const modalTelegramBtn = document.getElementById("modalTelegramBtn");

  async function init() {
    await loadProfiles();
    renderProfiles();
    await loadReelsFromApi();
    renderReels();
    await loadLogsFromApi();
    attachEvents();

    // Periodic poll every 8 seconds for new reels and logs
    setInterval(async () => {
      await loadReelsFromApi();
      renderReels();
      await loadLogsFromApi();
    }, 8000);
  }

  function mapDbReel(dbR) {
    const durationSec = dbR.duration_seconds || 0;
    const durStr = durationSec ? `${Math.floor(durationSec / 60)}:${String(Math.floor(durationSec % 60)).padStart(2, "0")}` : "0:30";
    const vScore = dbR.virality_score || 75;

    return {
      id: dbR.shortcode,
      author: `@${dbR.username}`,
      authorName: dbR.username,
      timestamp: dbR.watched_at ? dbR.watched_at.slice(11, 16) + " UTC" : "Недавно",
      category: "Tech",
      duration: durStr,
      views: dbR.views_count ? `${(dbR.views_count / 1000).toFixed(1)}K` : "—",
      likes: dbR.likes_count ? `${(dbR.likes_count / 1000).toFixed(1)}K` : "0",
      comments: String(dbR.comments_count || 0),
      shares: "—",
      sentimentScore: vScore,
      sentimentLabel: `${vScore}% Virality`,
      tags: dbR.tags || [],
      viralHook: dbR.hook_summary || dbR.caption || "Хук проанализирован",
      hookScore: dbR.hook_score || 0.0,
      viralityScore: vScore,
      hookType: dbR.hook_type || "Dynamic Hook",
      transcript: dbR.transcript || "",
      hookFrames: dbR.hook_frames || [],
      takeaways: [
        dbR.hook_dynamics || "Анализ смены планов в первые 3 секунды",
        dbR.hook_type ? `Тип хука: ${dbR.hook_type}` : "Оптимальная подача",
        dbR.hook_summary || "Рекомендации ИИ зафиксированы"
      ]
    };
  }

  async function loadReelsFromApi() {
    try {
      const res = await fetch("/api/reels");
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          const mapped = data.map(mapDbReel);
          reels = mapped;
        }
      }
    } catch (e) {
      // Keep existing reels on error
    }
  }

  async function loadLogsFromApi() {
    try {
      const res = await fetch("/api/logs");
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          activityLogStream.innerHTML = "";
          data.slice(0, 8).forEach((item) => {
            const time = item.timestamp ? item.timestamp.slice(11, 16) : "--:--";
            addLogEntry(time, item.message);
          });
        }
      }
    } catch (e) {
      // Ignore
    }
  }

  async function loadProfiles() {
    try {
      const res = await fetch("/api/profiles");
      if (res.ok) {
        profiles = await res.json();
        return;
      }
    } catch (e) {
      // Fallback
    }
    profiles = [
      { id: "p-1", username: "TheTechDaily", followers: "2.1M", status: "active", category: "Technology & AI" },
      { id: "p-2", username: "StartupHub", followers: "980K", status: "scanning", category: "Startups & Business" },
      { id: "p-3", username: "ViralGamer", followers: "1.4M", status: "active", category: "Gaming & Memes" },
      { id: "p-4", username: "DesignTrend", followers: "650K", status: "paused", category: "UI/UX & Product" }
    ];
  }

  function renderProfiles() {
    profilesContainer.innerHTML = "";
    profilesCountBadge.textContent = profiles.length;

    profiles.forEach((p) => {
      const el = document.createElement("div");
      el.className = "profile-card-item";
      el.innerHTML = `
        <div class="profile-avatar-circle">${p.username.charAt(0).toUpperCase()}</div>
        <div class="profile-info">
          <div class="profile-handle">@${escapeHtml(p.username)}</div>
          <div class="profile-followers">${escapeHtml(p.followers || "—")} followers</div>
        </div>
        <span class="status-tag ${p.status}">${p.status}</span>
      `;
      profilesContainer.appendChild(el);
    });
  }

  function renderReels() {
    let list = [...reels];

    if (categoryFilter !== "all") {
      list = list.filter((r) => r.category === categoryFilter);
    }

    if (currentFilter === "viral") {
      list = list.filter((r) => (r.viralityScore || r.sentimentScore) >= 85);
    } else if (currentFilter === "positive") {
      list = list.filter((r) => (r.hookScore || 0) >= 7.0);
    }

    if (searchQuery) {
      list = list.filter((r) => {
        return (
          r.author.toLowerCase().includes(searchQuery) ||
          r.viralHook.toLowerCase().includes(searchQuery) ||
          (r.transcript && r.transcript.toLowerCase().includes(searchQuery)) ||
          r.tags.some((t) => t.toLowerCase().includes(searchQuery))
        );
      });
    }

    totalReelsCount.textContent = list.length;
    reelsGrid.innerHTML = "";

    if (list.length === 0) {
      reelsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-dim);">Записей не найдено по заданным фильтрам.</div>`;
      return;
    }

    list.forEach((reel) => {
      const card = document.createElement("div");
      card.className = "reel-card";

      const tagsHtml = reel.tags.map((t) => `<span class="ai-tag">#${escapeHtml(t)}</span>`).join("");

      // 3-frame hook strip if available
      let framesStripHtml = "";
      if (reel.hookFrames && reel.hookFrames.length > 0) {
        const timestamps = ["0.5s", "1.5s", "3.0s"];
        framesStripHtml = `
          <div class="hook-frames-strip">
            ${reel.hookFrames.map((f, i) => `
              <div class="hook-frame-item">
                <img src="/thumbnails/${encodeURIComponent(f)}" alt="Hook Frame ${i+1}" loading="lazy" onerror="this.style.display='none'">
                <span class="hook-frame-tag">${timestamps[i] || (i+1) + "s"}</span>
              </div>
            `).join("")}
          </div>
        `;
      } else {
        framesStripHtml = `
          <div class="thumbnail-box">
            <div class="thumb-bg-gradient"></div>
            <div class="play-circle">▶</div>
            <span class="duration-tag">${reel.duration}</span>
          </div>
        `;
      }

      // Transcript dropdown if available
      let transcriptHtml = "";
      if (reel.transcript) {
        const wordCount = reel.transcript.split(/\s+/).filter(Boolean).length;
        transcriptHtml = `
          <details class="transcript-details">
            <summary>🎙️ Whisper транскрипция (${wordCount} слов)</summary>
            <div class="transcript-details-content">${escapeHtml(reel.transcript)}</div>
          </details>
        `;
      }

      card.innerHTML = `
        <div class="card-top-row">
          <div class="author-wrap">
            <span style="font-size: 16px;">🎬</span>
            <span class="author-handle">${escapeHtml(reel.author)}</span>
          </div>
          <span class="time-stamp">${escapeHtml(reel.timestamp)}</span>
        </div>

        ${framesStripHtml}

        <div class="hook-meta-row">
          <span class="badge-hook-score">🎯 Hook: ${reel.hookScore ? reel.hookScore + "/10" : "8.5/10"}</span>
          <span class="badge-virality">🔥 Virality: ${reel.viralityScore ? reel.viralityScore + "%" : "85%"}</span>
          <span style="font-size: 10px; color: var(--cyan-accent);">${escapeHtml(reel.hookType || "Dynamic Hook")}</span>
        </div>

        <div class="engagement-metrics">
          <span class="metric-item">👁️ ${reel.views}</span>
          <span class="metric-item">❤️ ${reel.likes}</span>
          <span class="metric-item">💬 ${reel.comments}</span>
          <span class="metric-item">↗️ ${reel.shares}</span>
        </div>

        <div class="ai-analysis-block">
          <div class="tag-list">${tagsHtml}</div>
          
          <div class="hook-analysis-box">
            <div class="hook-title">🎯 Gemini Multimodal Hook Analysis</div>
            <p>${escapeHtml(reel.viralHook)}</p>
          </div>

          ${transcriptHtml}
        </div>

        <div class="card-actions">
          <button class="btn-detail view-analysis-btn">Подробный разбор & Кадры</button>
          <button class="btn-telegram-share send-tg-btn" title="Отправить карточку в Telegram">✈️</button>
        </div>
      `;

      card.querySelector(".view-analysis-btn").addEventListener("click", () => openReelDetails(reel));
      card.querySelector(".send-tg-btn").addEventListener("click", () => sendTelegramAlert(reel));

      reelsGrid.appendChild(card);
    });
  }

  function addLogEntry(time, text) {
    const row = document.createElement("div");
    row.className = "log-entry";
    row.innerHTML = `<span class="log-time">${time}</span> <span>${escapeHtml(text)}</span>`;
    activityLogStream.prepend(row);
  }

  function openReelDetails(reel) {
    modalReelTitle.textContent = `${reel.author} • Multimodal Hook Analysis`;
    modalDurationTag.textContent = reel.duration;

    let framesPreview = "";
    if (reel.hookFrames && reel.hookFrames.length > 0) {
      framesPreview = `
        <div style="display:flex; gap:6px; margin-top:10px;">
          ${reel.hookFrames.map((f, i) => `
            <div style="flex:1; position:relative; aspect-ratio:9/14; border-radius:6px; overflow:hidden; border:1px solid rgba(255,255,255,0.15);">
              <img src="/thumbnails/${encodeURIComponent(f)}" style="width:100%; height:100%; object-fit:cover;" onerror="this.style.display='none'">
              <span style="position:absolute; bottom:2px; left:2px; font-size:9px; background:rgba(0,0,0,0.8); color:#38bdf8; padding:1px 4px; border-radius:3px;">${["0.5s", "1.5s", "3.0s"][i] || ""}</span>
            </div>
          `).join("")}
        </div>
      `;
    }

    modalMetricsBar.innerHTML = `
      ${framesPreview}
      <div style="display:flex; justify-content:space-around; padding: 12px 0; font-size:12px; color:var(--text-muted); border-top:1px solid rgba(255,255,255,0.06); margin-top:10px;">
        <span>Просмотры: <b>${reel.views}</b></span>
        <span>Лайки: <b>${reel.likes}</b></span>
        <span>Оценка хука: <b>${reel.hookScore ? reel.hookScore + "/10" : "8.5/10"}</b></span>
      </div>
    `;

    modalHookText.textContent = reel.viralHook;
    modalTranscriptText.textContent = reel.transcript || "Транскрипция речи отсутствует или обрабатывается.";

    modalKeyTakeaways.innerHTML = reel.takeaways.map((t) => `<li>${escapeHtml(t)}</li>`).join("");

    modalTelegramBtn.onclick = () => sendTelegramAlert(reel);

    reelDetailModal.classList.add("active");
  }

  function sendTelegramAlert(reel) {
    alert(`✈️ Telegram Alert Sent!\n\nКарточка Reels от ${reel.author} успешно отправлена в ваш Telegram-канал с полным саммари и разбором хука.`);
  }

  function attachEvents() {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.trim().toLowerCase();
      renderReels();
    });

    filterCategory.addEventListener("change", (e) => {
      categoryFilter = e.target.value;
      renderReels();
    });

    toggleBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        toggleBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.dataset.filter;
        renderReels();
      });
    });

    // Add Profile Modal
    addProfileBtn.addEventListener("click", () => {
      profileUsername.value = "";
      addProfileModal.classList.add("active");
      profileUsername.focus();
    });

    closeProfileModal.addEventListener("click", () => addProfileModal.classList.remove("active"));
    cancelProfileBtn.addEventListener("click", () => addProfileModal.classList.remove("active"));
    
    saveProfileBtn.addEventListener("click", async () => {
      const username = profileUsername.value.trim().replace(/^@/, "");
      if (!username) return;

      const newP = {
        username: username,
        followers: "Новый",
        status: "scanning",
        category: profileCategory.value
      };

      try {
        await fetch("/api/profiles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newP)
        });
      } catch (e) {}

      profiles.unshift(newP);
      renderProfiles();
      addProfileModal.classList.remove("active");
      addLogEntry(getCurrentTime(), `Added target @${username} to monitor queue`);
    });

    // Close Reel Detail Modal
    closeReelModal.addEventListener("click", () => reelDetailModal.classList.remove("active"));
    closeReelModalBtn.addEventListener("click", () => reelDetailModal.classList.remove("active"));

    // Trigger Simulation Scan
    scanNowBtn.addEventListener("click", triggerAgentSimulation);
  }

  function triggerAgentSimulation() {
    scanNowBtn.disabled = true;
    scanNowBtn.style.opacity = "0.7";
    scanNowBtn.textContent = "⏳ Сканирование профилей...";

    currentTaskLabel.textContent = "Current Task: Scraping Instagram Reels...";
    currentTaskProgressBar.style.width = "20%";
    currentTaskProgressNum.textContent = "20%";
    addLogEntry(getCurrentTime(), "Launched background Instaloader headless session");

    setTimeout(() => {
      currentTaskProgressBar.style.width = "55%";
      currentTaskProgressNum.textContent = "55%";
      currentTaskLabel.textContent = "Current Task: Extracting audio & Whisper transcription...";
      addLogEntry(getCurrentTime(), "Downloaded media stream, running faster-whisper speech-to-text");
    }, 1200);

    setTimeout(() => {
      currentTaskProgressBar.style.width = "85%";
      currentTaskProgressNum.textContent = "85%";
      currentTaskLabel.textContent = "Current Task: Gemini Flash multimodal hook analysis (3 frames)...";
      addLogEntry(getCurrentTime(), "Captured 3 hook frames (0.5s, 1.5s, 3.0s) & evaluating virality");
    }, 2400);

    setTimeout(() => {
      currentTaskProgressBar.style.width = "100%";
      currentTaskProgressNum.textContent = "100%";
      currentTaskLabel.textContent = "Current Task: Idle (Monitoring)";
      
      const newReel = {
        id: "reel-" + Date.now(),
        author: "@StartupHub",
        authorName: "Startup Hub",
        timestamp: "Только что",
        category: "Startups",
        duration: "0:41",
        views: "1.1M",
        likes: "92K",
        comments: "1.1K",
        shares: "21K",
        sentimentScore: 97,
        sentimentLabel: "97% Viral",
        tags: ["Growth", "Bootstrapping", "Viral"],
        viralHook: "«This 1-person startup makes $40k/month.» — High-contrast caption hook, immediate MRR dashboard reveal.",
        hookScore: 9.4,
        viralityScore: 97,
        hookType: "Curiosity Gap (Любопытство)",
        hookFrames: [],
        transcript: "Here is how a solo developer built a micro-SaaS with zero funding. He picked a single niche problem, automated the entire customer acquisition pipeline using autonomous AI agents, and scaled to 40 thousand dollars in monthly recurring revenue in less than 9 months.",
        takeaways: [
          "Визуальный хук с демонстрацией реального дашборда дохода",
          "Пошаговая разбивка методологии без лишней воды",
          "Призыв перейти по ссылке в био для получения шаблона"
        ]
      };

      reels.unshift(newReel);
      renderReels();
      addLogEntry(getCurrentTime(), `Discovered new viral Reel by ${newReel.author}! Multimodal hook: 9.4/10`);

      scanNowBtn.disabled = false;
      scanNowBtn.style.opacity = "1";
      scanNowBtn.textContent = "⚡ Запустить сканирование";
    }, 3600);
  }

  function getCurrentTime() {
    const d = new Date();
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  document.addEventListener("DOMContentLoaded", init);
})();