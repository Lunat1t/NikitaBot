// NikitaBot AI Reels Agent Dashboard Logic - Sales & Marketing Edition
(function () {
  "use strict";

  let reels = [];
  let profiles = [];
  let activeProfile = null; // null means 'all profiles'
  let currentFilter = "all";
  let searchQuery = "";
  let categoryFilter = "all";
  let currentTab = "reels"; // 'reels' or 'audit'
  let currentModalReel = null;

  // DOM Elements
  const profilesContainer = document.getElementById("profilesContainer");
  const reelsGrid = document.getElementById("reelsGrid");
  const totalReelsCount = document.getElementById("totalReelsCount");
  const tabReelsCount = document.getElementById("tabReelsCount");
  const searchInput = document.getElementById("searchInput");
  const filterCategory = document.getElementById("filterCategory");
  const toggleBtns = document.querySelectorAll(".toggle-btn");
  const scanNowBtn = document.getElementById("scanNowBtn");
  const activityLogStream = document.getElementById("activityLogStream");
  const breadcrumbActiveProfile = document.getElementById("breadcrumbActiveProfile");

  // Hero Profile Banner
  const profileHeroBanner = document.getElementById("profileHeroBanner");
  const heroAvatar = document.getElementById("heroAvatar");
  const heroHandle = document.getElementById("heroHandle");
  const heroCategory = document.getElementById("heroCategory");
  const heroDesc = document.getElementById("heroDesc");
  const heroStatWatched = document.getElementById("heroStatWatched");
  const heroStatViews = document.getElementById("heroStatViews");
  const heroStatHook = document.getElementById("heroStatHook");
  const heroStatLead = document.getElementById("heroStatLead");
  const btnDeleteActiveProfile = document.getElementById("btnDeleteActiveProfile");

  // Tabs
  const tabReelsBtn = document.getElementById("tabReelsBtn");
  const tabAuditBtn = document.getElementById("tabAuditBtn");
  const reelsFeedSection = document.getElementById("reelsFeedSection");
  const auditContentSection = document.getElementById("auditContentSection");
  const navAllProfilesBtn = document.getElementById("navAllProfilesBtn");
  const navAuditModeBtn = document.getElementById("navAuditModeBtn");

  // Audit Tab Elements
  const auditStrengthsList = document.getElementById("auditStrengthsList");
  const auditWeaknessesList = document.getElementById("auditWeaknessesList");
  const auditGrowthList = document.getElementById("auditGrowthList");
  const salesPitchTextBox = document.getElementById("salesPitchTextBox");
  const copyPitchBtn = document.getElementById("copyPitchBtn");
  const copyPitchText = document.getElementById("copyPitchText");
  const copyPitchIcon = document.getElementById("copyPitchIcon");
  const refreshAuditBtn = document.getElementById("refreshAuditBtn");

  // Add Profile Modal
  const addProfileBtn = document.getElementById("addProfileBtn");
  const addProfileModal = document.getElementById("addProfileModal");
  const closeProfileModal = document.getElementById("closeProfileModal");
  const cancelProfileBtn = document.getElementById("cancelProfileBtn");
  const saveProfileBtn = document.getElementById("saveProfileBtn");
  const profileUsername = document.getElementById("profileUsername");
  const profileCategory = document.getElementById("profileCategory");

  // Reel Detail Modal
  const reelDetailModal = document.getElementById("reelDetailModal");
  const closeReelModal = document.getElementById("closeReelModal");
  const closeReelModalBtn = document.getElementById("closeReelModalBtn");
  const modalReelTitle = document.getElementById("modalReelTitle");
  const modalDurationTag = document.getElementById("modalDurationTag");
  const modalMetricsBar = document.getElementById("modalMetricsBar");
  const modalHookText = document.getElementById("modalHookText");
  const modalTranscriptText = document.getElementById("modalTranscriptText");
  const modalKeyTakeaways = document.getElementById("modalKeyTakeaways");

  async function init() {
    await loadProfiles();
    renderProfiles();
    await loadReelsFromApi();
    renderReels();
    await loadLogsFromApi();
    attachEvents();

    // Auto-refresh every 10 seconds (skip grid re-render if user is watching a reel)
    setInterval(async () => {
      await loadProfiles();
      renderProfiles();
      await loadLogsFromApi();
      if (!reelDetailModal || !reelDetailModal.classList.contains("active")) {
        await loadReelsFromApi();
        renderReels();
      }
    }, 10000);
  }

  function mapDbReel(dbR) {
    const durationSec = dbR.duration_seconds || 0;
    const durStr = durationSec ? `${Math.floor(durationSec / 60)}:${String(Math.floor(durationSec % 60)).padStart(2, "0")}` : "0:30";
    const vScore = dbR.virality_score || 75;

    return {
      id: dbR.shortcode,
      author: `@${dbR.username}`,
      authorName: dbR.username,
      timestamp: dbR.watched_at ? dbR.watched_at.slice(0, 16).replace("T", " ") : "Недавно",
      watchedAt: dbR.watched_at,
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
      videoUrl: dbR.video_url || (dbR.shortcode ? `/videos/${dbR.shortcode}.mp4` : null),
      thumbnailUrl: dbR.thumbnail_url || (dbR.hook_frames && dbR.hook_frames.length ? `/thumbnails/${dbR.hook_frames[0]}` : null),
      takeaways: [
        dbR.hook_dynamics || "Анализ смены планов в первые 3 секунды",
        dbR.hook_type ? `Тип хука: ${dbR.hook_type}` : "Оптимальная подача",
        dbR.hook_summary || "Рекомендации ИИ зафиксированы"
      ]
    };
  }

  async function loadProfiles() {
    try {
      const res = await fetch("/api/profiles");
      if (res.ok) {
        profiles = await res.json();
        return;
      }
    } catch (e) {}

    profiles = [
      { username: "sentimentalka_smm", category: "Marketing & Growth", followers: "Новый", stats: { total_reels: 0, total_views: 0, avg_hook_score: 0.0, avg_virality: 0 } },
      { username: "TheTechDaily", category: "Technology & AI", followers: "2.1M", stats: { total_reels: 2, total_views: 4100000, avg_hook_score: 9.3, avg_virality: 95 } },
      { username: "StartupHub", category: "Startups & Business", followers: "980K", stats: { total_reels: 1, total_views: 890000, avg_hook_score: 8.7, avg_virality: 88 } }
    ];
  }

  function renderProfiles() {
    profilesContainer.innerHTML = "";

    profiles.forEach((p) => {
      const el = document.createElement("div");
      const isActive = activeProfile && activeProfile.toLowerCase() === p.username.toLowerCase();
      el.className = `profile-card-item ${isActive ? "active" : ""}`;
      
      const reelsCount = p.stats ? p.stats.total_reels : 0;
      const reelsLabel = reelsCount > 0 ? `🎬 ${reelsCount} reels` : "нет рилсов";

      el.innerHTML = `
        <div class="profile-avatar-circle">${p.username.charAt(0).toUpperCase()}</div>
        <div class="profile-info">
          <div class="profile-handle">@${escapeHtml(p.username)}</div>
          <div class="profile-followers">${reelsLabel} • ${escapeHtml(p.category || "Общий")}</div>
        </div>
        <button class="btn-profile-del" title="Удалить из отслеживаемых" data-username="${escapeHtml(p.username)}">✕</button>
      `;

      // Select profile
      el.addEventListener("click", (e) => {
        if (e.target.classList.contains("btn-profile-del")) {
          e.stopPropagation();
          deleteProfile(p.username);
          return;
        }
        selectProfile(p.username);
      });

      profilesContainer.appendChild(el);
    });
  }

  function selectProfile(username) {
    activeProfile = username;
    breadcrumbActiveProfile.textContent = `@${username}`;
    renderProfiles();
    updateHeroBanner();
    renderReels();
    loadProfileAudit(username);
  }

  function resetToAllProfiles() {
    activeProfile = null;
    breadcrumbActiveProfile.textContent = "Все профили";
    profileHeroBanner.style.display = "none";
    renderProfiles();
    renderReels();
    switchTab("reels");
  }

  function updateHeroBanner() {
    if (!activeProfile) {
      profileHeroBanner.style.display = "none";
      return;
    }

    profileHeroBanner.style.display = "flex";
    heroAvatar.textContent = activeProfile.charAt(0).toUpperCase();
    heroHandle.textContent = `@${activeProfile}`;

    const prof = profiles.find((p) => p.username.toLowerCase() === activeProfile.toLowerCase());
    heroCategory.textContent = prof ? (prof.category || "General") : "General";

    const stats = prof && prof.stats ? prof.stats : { total_reels: 0, total_views: 0, avg_hook_score: 0.0, avg_virality: 0 };
    heroStatWatched.textContent = stats.total_reels || 0;
    heroStatViews.textContent = stats.total_views > 1000 ? `${(stats.total_views / 1000).toFixed(1)}K` : stats.total_views;
    heroStatHook.textContent = stats.avg_hook_score > 0 ? stats.avg_hook_score : "—";
    heroStatLead.textContent = stats.total_reels > 0 ? Math.min(98, 70 + stats.total_reels * 4) : "—";

    heroDesc.textContent = `Автономный агент отслеживает @${activeProfile}: просмотрено ${stats.total_reels} рилсов, готовит Sales & Marketing аудит.`;
  }

  async function deleteProfile(username) {
    if (!confirm(`Удалить профиль @${username} из отслеживаемых?`)) return;

    try {
      await fetch(`/api/profiles/${encodeURIComponent(username)}`, { method: "DELETE" });
      profiles = profiles.filter((p) => p.username.toLowerCase() !== username.toLowerCase());
      if (activeProfile && activeProfile.toLowerCase() === username.toLowerCase()) {
        resetToAllProfiles();
      } else {
        renderProfiles();
      }
    } catch (e) {
      alert("Ошибка при удалении профиля");
    }
  }

  async function loadReelsFromApi() {
    try {
      const url = activeProfile ? `/api/reels?username=${encodeURIComponent(activeProfile)}` : "/api/reels";
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          reels = data.map(mapDbReel);
        } else if (activeProfile) {
          reels = [];
        }
      }
    } catch (e) {}
  }

  function renderReels() {
    let list = [...reels];

    if (activeProfile) {
      list = list.filter((r) => r.authorName.toLowerCase() === activeProfile.toLowerCase());
    }

    if (categoryFilter !== "all") {
      list = list.filter((r) => r.category === categoryFilter);
    }

    if (currentFilter === "viral") {
      list = list.filter((r) => (r.viralityScore || 0) >= 85);
    } else if (currentFilter === "positive") {
      list = list.filter((r) => (r.hookScore || 0) >= 7.5);
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
    tabReelsCount.textContent = list.length;
    reelsGrid.innerHTML = "";

    if (list.length === 0) {
      const msg = activeProfile
        ? `У профиля @${activeProfile} пока нет просмотренных роликов. Нажмите «⚡ Запустить сканирование» или введите команду watch в CLI.`
        : `Нет просмотренных рилсов по заданным фильтрам.`;
      reelsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-dim);">${msg}</div>`;
      return;
    }

    list.forEach((reel) => {
      const card = document.createElement("div");
      card.className = "reel-card";

      const tagsHtml = reel.tags.map((t) => `<span class="ai-tag">#${escapeHtml(t)}</span>`).join("");

      // 3-frame hook strip
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

      // Transcript dropdown
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

      const sc = reel.shortcode || reel.id || "";
      let cardVideoUrl = reel.videoUrl;
      if (!cardVideoUrl || cardVideoUrl.startsWith("http://") || cardVideoUrl.startsWith("https://")) {
        cardVideoUrl = `/videos/${encodeURIComponent(sc)}.mp4`;
      }

      card.innerHTML = `
        <div class="card-top-row">
          <div class="author-wrap">
            <span style="font-size: 16px;">🎬</span>
            <span class="author-handle">${escapeHtml(reel.author)}</span>
          </div>
          <span class="time-stamp">✅ Просмотрен ${escapeHtml(reel.timestamp)}</span>
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
        </div>

        <div class="ai-analysis-block">
          <div class="tag-list">${tagsHtml}</div>
          
          <div class="hook-analysis-box">
            <div class="hook-title">🎯 Разбор хука & Рекомендации</div>
            <p>${escapeHtml(reel.viralHook)}</p>
          </div>

          ${transcriptHtml}
        </div>

        <div class="card-actions" style="display: flex; gap: 8px;">
          <button class="btn-play-reel watch-reel-btn" style="flex: 1; background: linear-gradient(135deg, #059669, #10b981); color: white; border: none; padding: 8px 10px; border-radius: 8px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 12px; transition: transform 0.15s ease;">
            <span>▶️ Смотреть Reel</span>
          </button>
          <button class="btn-detail view-analysis-btn" style="flex: 1; cursor: pointer;">Разбор & Кадры</button>
          <button class="btn-delete-reel delete-reel-card-btn" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 8px 10px; cursor: pointer; font-size: 13px; transition: all 0.2s;" title="Удалить этот Reel">
            🗑
          </button>
        </div>
        ${cardVideoUrl ? `
          <div style="margin-top: 8px; text-align: center;">
            <a href="${cardVideoUrl}" target="_blank" style="font-size: 11px; color: #38bdf8; text-decoration: underline; opacity: 0.85;" title="Открыть исходный файл H.264 MP4">
              ↗ Открыть видео напрямую (${escapeHtml(sc)}.mp4)
            </a>
          </div>
        ` : ""}
      `;

      const watchBtn = card.querySelector(".watch-reel-btn");
      if (watchBtn) {
        watchBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          openReelDetails(reel, true);
        });
      }

      const viewBtn = card.querySelector(".view-analysis-btn");
      if (viewBtn) {
        viewBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          openReelDetails(reel, false);
        });
      }

      const delBtn = card.querySelector(".delete-reel-card-btn");
      if (delBtn) {
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          confirmAndDeleteReel(reel.shortcode || reel.id, false);
        });
      }

      // Allow clicking on frames strip or thumbnail box to also open details
      const frameEl = card.querySelector(".hook-frames-strip, .thumbnail-box");
      if (frameEl) {
        frameEl.style.cursor = "pointer";
        frameEl.title = "Нажмите для подробного разбора и просмотра";
        frameEl.addEventListener("click", () => openReelDetails(reel, false));
      }

      reelsGrid.appendChild(card);
    });
  }

  async function loadProfileAudit(username) {
    const cleanUser = username.replace("@", "");
    auditStrengthsList.innerHTML = "<li>Загрузка сильных сторон...</li>";
    auditWeaknessesList.innerHTML = "<li>Загрузка ошибок и уязвимостей...</li>";
    auditGrowthList.innerHTML = "<li>Загрузка точек роста...</li>";
    salesPitchTextBox.textContent = "Формирование коммерческого предложения...";

    try {
      const res = await fetch(`/api/profiles/${encodeURIComponent(cleanUser)}/audit`);
      if (res.ok) {
        const audit = await res.json();
        renderAudit(audit);
      }
    } catch (e) {
      salesPitchTextBox.textContent = "Не удалось загрузить аудит.";
    }
  }

  function renderAudit(audit) {
    if (!audit) return;

    auditStrengthsList.innerHTML = (audit.strengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
    auditWeaknessesList.innerHTML = (audit.weaknesses || []).map((w) => `<li>${escapeHtml(w)}</li>`).join("");
    auditGrowthList.innerHTML = (audit.growth_points || []).map((g) => `<li>${escapeHtml(g)}</li>`).join("");
    salesPitchTextBox.textContent = audit.sales_pitch || "Питч генерируется...";
  }

  function switchTab(tab) {
    currentTab = tab;
    if (tab === "reels") {
      tabReelsBtn.classList.add("active");
      tabAuditBtn.classList.remove("active");
      reelsFeedSection.style.display = "block";
      auditContentSection.style.display = "none";
    } else {
      tabAuditBtn.classList.add("active");
      tabReelsBtn.classList.remove("active");
      reelsFeedSection.style.display = "none";
      auditContentSection.style.display = "block";
      if (!activeProfile && profiles.length > 0) {
        selectProfile(profiles[0].username);
      } else if (activeProfile) {
        loadProfileAudit(activeProfile);
      }
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
    } catch (e) {}
  }

  function addLogEntry(time, text) {
    const row = document.createElement("div");
    row.className = "log-entry";
    row.innerHTML = `<span class="log-time">${time}</span> <span>${escapeHtml(text)}</span>`;
    activityLogStream.prepend(row);
  }

  function openReelDetails(reel, autoPlay = false) {
    if (!reel) return;
    currentModalReel = reel;
    const sc = reel.shortcode || reel.id || "";
    try {
      if (modalReelTitle) {
        modalReelTitle.textContent = `${reel.author} • Разбор и кадры`;
      }
      const durTag = document.getElementById("modalDurationTag");
      if (durTag) {
        durTag.textContent = reel.duration || "0:30";
      }

      // Always resolve to safe local endpoint to prevent Instagram CDN CORS/403 errors
      let streamUrl = reel.videoUrl;
      if (!streamUrl || streamUrl.startsWith("http://") || streamUrl.startsWith("https://")) {
        streamUrl = `/videos/${encodeURIComponent(sc)}.mp4`;
      }

      const modalVideoPlayer = document.getElementById("modalVideoPlayer");
      const modalDirectVideoLink = document.getElementById("modalDirectVideoLink");
      if (modalVideoPlayer) {
        if (streamUrl) {
          modalVideoPlayer.src = streamUrl;
          if (reel.thumbnailUrl) modalVideoPlayer.poster = reel.thumbnailUrl;
          modalVideoPlayer.load();
          if (autoPlay) {
            const playPromise = modalVideoPlayer.play();
            if (playPromise !== undefined) {
              playPromise.catch((err) => {
                console.warn("Autoplay deferred or requires user gesture:", err);
              });
            }
          }
        } else {
          modalVideoPlayer.removeAttribute("src");
        }
      }
      if (modalDirectVideoLink) {
        if (streamUrl) {
          modalDirectVideoLink.href = streamUrl;
          modalDirectVideoLink.style.display = "block";
          modalDirectVideoLink.textContent = `↗ Открыть видео напрямую (${sc || "Reel"}.mp4)`;
        } else {
          modalDirectVideoLink.style.display = "none";
        }
      }

      let framesPreview = "";
      if (reel.hookFrames && reel.hookFrames.length > 0) {
        framesPreview = `
          <div style="margin-top:10px;">
            <div style="font-size:11px; color:var(--cyan-accent); font-weight:600; margin-bottom:6px;">📸 Раскадровка хука (0.5s, 1.5s, 3.0s):</div>
            <div style="display:flex; gap:6px;">
              ${reel.hookFrames.map((f, i) => `
                <div style="flex:1; position:relative; aspect-ratio:9/14; border-radius:6px; overflow:hidden; border:1px solid rgba(255,255,255,0.15); background:#000;">
                  <img src="/thumbnails/${encodeURIComponent(f)}" style="width:100%; height:100%; object-fit:cover;" onerror="this.style.display='none'">
                  <span style="position:absolute; bottom:2px; left:2px; font-size:9px; background:rgba(0,0,0,0.8); color:#38bdf8; padding:1px 4px; border-radius:3px;">${["0.5s", "1.5s", "3.0s"][i] || ""}</span>
                </div>
              `).join("")}
            </div>
          </div>
        `;
      }

      if (modalMetricsBar) {
        modalMetricsBar.innerHTML = `
          ${framesPreview}
          <div style="display:flex; justify-content:space-around; padding: 12px 0; font-size:12px; color:var(--text-muted); border-top:1px solid rgba(255,255,255,0.06); margin-top:10px;">
            <span>Просмотры: <b>${reel.views}</b></span>
            <span>Лайки: <b>${reel.likes}</b></span>
            <span>Оценка хука: <b>${reel.hookScore ? reel.hookScore + "/10" : "8.5/10"}</b></span>
          </div>
        `;
      }

      if (modalHookText) {
        modalHookText.textContent = reel.viralHook || "Хук проанализирован";
      }
      if (modalTranscriptText) {
        modalTranscriptText.textContent = reel.transcript || "Транскрипция речи отсутствует или обрабатывается.";
      }
      if (modalKeyTakeaways) {
        const takeaways = Array.isArray(reel.takeaways) ? reel.takeaways : [];
        modalKeyTakeaways.innerHTML = takeaways.map((t) => `<li>${escapeHtml(t)}</li>`).join("");
      }

      if (reelDetailModal) {
        reelDetailModal.classList.add("active");
      }
    } catch (err) {
      console.error("Error opening reel detail modal:", err);
      if (reelDetailModal) reelDetailModal.classList.add("active");
    }
  }

  function closeDetailModal() {
    const modalVideoPlayer = document.getElementById("modalVideoPlayer");
    if (modalVideoPlayer) {
      try {
        modalVideoPlayer.pause();
        modalVideoPlayer.currentTime = 0;
      } catch (e) {}
    }
    if (reelDetailModal) {
      reelDetailModal.classList.remove("active");
    }
  }

  async function confirmAndDeleteReel(shortcode, fromModal = false) {
    if (!shortcode) return;
    if (!confirm(`Удалить ролик (${shortcode}) из ленты и базы данных?`)) {
      return;
    }

    try {
      const res = await fetch(`/api/reels/${encodeURIComponent(shortcode)}`, {
        method: "DELETE"
      });
      if (res.ok) {
        if (fromModal) {
          closeDetailModal();
        }
        // Remove reel from local state
        reels = reels.filter((r) => (r.shortcode || r.id) !== shortcode);
        renderReels(reels);
        showNotification("Ролик успешно удален из ленты", "success");
        // Refresh profile stats and logs
        loadProfilesFromApi();
        loadLogsFromApi();
      } else {
        showNotification("Не удалось удалить ролик", "error");
      }
    } catch (err) {
      console.error("Delete reel error:", err);
      showNotification("Ошибка сети при удалении ролика", "error");
    }
  }

  function attachEvents() {
    // Top Tabs
    tabReelsBtn.addEventListener("click", () => switchTab("reels"));
    tabAuditBtn.addEventListener("click", () => switchTab("audit"));
    navAllProfilesBtn.addEventListener("click", resetToAllProfiles);
    navAuditModeBtn.addEventListener("click", () => switchTab("audit"));

    // Delete active profile from banner
    btnDeleteActiveProfile.addEventListener("click", () => {
      if (activeProfile) deleteProfile(activeProfile);
    });

    // Copy Sales Pitch
    copyPitchBtn.addEventListener("click", () => {
      const text = salesPitchTextBox.textContent;
      if (!text) return;
      navigator.clipboard.writeText(text).then(() => {
        copyPitchIcon.textContent = "✅";
        copyPitchText.textContent = "Скопировано в буфер!";
        setTimeout(() => {
          copyPitchIcon.textContent = "📋";
          copyPitchText.textContent = "Скопировать Sales Pitch";
        }, 2200);
      });
    });

    // Refresh Audit
    refreshAuditBtn.addEventListener("click", async () => {
      if (!activeProfile) return;
      refreshAuditBtn.disabled = true;
      refreshAuditBtn.textContent = "⏳ Перегенерация...";
      try {
        const res = await fetch(`/api/profiles/${encodeURIComponent(activeProfile)}/audit`, { method: "POST" });
        if (res.ok) {
          const newAudit = await res.json();
          renderAudit(newAudit);
        }
      } catch (e) {}
      refreshAuditBtn.disabled = false;
      refreshAuditBtn.textContent = "🔄 Перегенерировать аудит";
    });

    // Search & Category Filters
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
      let rawVal = profileUsername.value.trim();
      if (!rawVal) return;

      // Extract username if URL is pasted
      if (rawVal.includes("instagram.com/")) {
        const m = rawVal.match(/instagram\.com\/([A-Za-z0-9_.]+)/);
        if (m) rawVal = m[1];
      }
      const username = rawVal.replace(/^@/, "").split("?")[0].replace(/\/$/, "");

      const newP = {
        username: username,
        followers: "Новый",
        status: "active",
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
      selectProfile(username);
    });

    // Close Reel Detail Modal & stop playback
    if (closeReelModal) closeReelModal.addEventListener("click", closeDetailModal);
    if (closeReelModalBtn) closeReelModalBtn.addEventListener("click", closeDetailModal);
    if (reelDetailModal) {
      reelDetailModal.addEventListener("click", (e) => {
        if (e.target === reelDetailModal) closeDetailModal();
      });
    }
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && reelDetailModal && reelDetailModal.classList.contains("active")) {
        closeDetailModal();
      }
    });

    const modalDeleteReelBtn = document.getElementById("modalDeleteReelBtn");
    if (modalDeleteReelBtn) {
      modalDeleteReelBtn.addEventListener("click", () => {
        if (currentModalReel) {
          const sc = currentModalReel.shortcode || currentModalReel.id;
          confirmAndDeleteReel(sc, true);
        }
      });
    }

    // Watch Reel / Video by direct URL Modal
    const openWatchUrlModalBtn = document.getElementById("openWatchUrlModalBtn");
    const watchUrlModal = document.getElementById("watchUrlModal");
    const closeWatchUrlModal = document.getElementById("closeWatchUrlModal");
    const cancelWatchUrlBtn = document.getElementById("cancelWatchUrlBtn");
    const startWatchUrlBtn = document.getElementById("startWatchUrlBtn");
    const watchUrlInput = document.getElementById("watchUrlInput");

    if (openWatchUrlModalBtn && watchUrlModal) {
      openWatchUrlModalBtn.addEventListener("click", () => {
        watchUrlInput.value = "";
        watchUrlModal.classList.add("active");
        watchUrlInput.focus();
      });
      closeWatchUrlModal.addEventListener("click", () => watchUrlModal.classList.remove("active"));
      cancelWatchUrlBtn.addEventListener("click", () => watchUrlModal.classList.remove("active"));
      startWatchUrlBtn.addEventListener("click", async () => {
        const targetUrl = watchUrlInput.value.trim();
        if (!targetUrl) return;
        startWatchUrlBtn.disabled = true;
        startWatchUrlBtn.textContent = "⏳ Анализ...";
        try {
          await fetch("/api/watch-url", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: targetUrl })
          });
        } catch (e) {}
        watchUrlModal.classList.remove("active");
        startWatchUrlBtn.disabled = false;
        startWatchUrlBtn.textContent = "▶️ Смотреть и анализировать";
        addLogEntry(getCurrentTime(), `Запущен прямой анализ видео: ${targetUrl}`);
        setTimeout(async () => {
          await loadReelsFromApi();
          renderReels();
        }, 3000);
      });
    }

    // Trigger Real Live Scan via API
    scanNowBtn.addEventListener("click", async () => {
      const targetUser = activeProfile || (profiles.length > 0 ? profiles[0].username : "sentimentalka_smm");
      scanNowBtn.disabled = true;
      scanNowBtn.style.opacity = "0.7";
      scanNowBtn.innerHTML = `<span>⏳ Сканирую @${escapeHtml(targetUser)}...</span>`;

      addLogEntry(getCurrentTime(), `Запущен автономный просмотр контента @${targetUser}`);

      try {
        await fetch("/api/scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: targetUser })
        });
      } catch (e) {
        console.error("Scan trigger error:", e);
      }

      // Wait briefly for first reels to be processed, then refresh
      setTimeout(async () => {
        await loadProfiles();
        renderProfiles();
        await loadReelsFromApi();
        renderReels();
        if (activeProfile) {
          updateHeroBanner();
          loadProfileAudit(activeProfile);
        }

        scanNowBtn.disabled = false;
        scanNowBtn.style.opacity = "1";
        scanNowBtn.innerHTML = `<span>⚡ Запустить сканирование</span>`;
      }, 4000);
    });
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