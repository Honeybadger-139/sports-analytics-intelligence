document.addEventListener("DOMContentLoaded", () => {
    const API_BASE = "/api/v1";
    const CURRENT_SEASON = "2025-26";
    const THEME_KEY = "sai_theme";

    const dom = {
        overallStatus: document.getElementById("overall-status"),
        refreshAllBtn: document.getElementById("refresh-all-btn"),
        themeToggleBtn: document.getElementById("theme-toggle-btn"),

        tabButtons: Array.from(document.querySelectorAll(".tab-btn")),
        tabPanels: Array.from(document.querySelectorAll(".tab-panel")),

        rawTableSelect: document.getElementById("raw-table-select"),
        rawSeasonInput: document.getElementById("raw-season-input"),
        rawLimitInput: document.getElementById("raw-limit-input"),
        rawLoadBtn: document.getElementById("raw-load-btn"),
        rawRefreshBtn: document.getElementById("raw-refresh-btn"),
        rawPrevBtn: document.getElementById("raw-prev-btn"),
        rawNextBtn: document.getElementById("raw-next-btn"),
        rawMeta: document.getElementById("raw-meta"),
        rawHead: document.getElementById("raw-head"),
        rawBody: document.getElementById("raw-body"),

        qualitySeasonInput: document.getElementById("quality-season-input"),
        qualityLoadBtn: document.getElementById("quality-load-btn"),
        qualityRefreshBtn: document.getElementById("quality-refresh-btn"),
        qMatches: document.getElementById("q-matches"),
        qTeams: document.getElementById("q-teams"),
        qPlayers: document.getElementById("q-players"),
        qTeamStats: document.getElementById("q-team-stats"),
        qPlayerStats: document.getElementById("q-player-stats"),
        qAvgIngest: document.getElementById("q-avg-ingest"),
        qAvgFeature: document.getElementById("q-avg-feature"),
        qLatestIngest: document.getElementById("q-latest-ingest"),
        qLatestFeature: document.getElementById("q-latest-feature"),
        qualityCheckBody: document.getElementById("quality-check-body"),
        qualityTeamBody: document.getElementById("quality-team-body"),
        qualityRunBody: document.getElementById("quality-run-body"),

        refreshTodayBtn: document.getElementById("refresh-today-btn"),
        refreshAuditBtn: document.getElementById("refresh-audit-btn"),
        refreshBankrollBtn: document.getElementById("refresh-bankroll-btn"),
        dbStatus: document.getElementById("db-status"),
        pipelineStatus: document.getElementById("pipeline-status"),
        lastSync: document.getElementById("last-sync"),
        matchCount: document.getElementById("match-count"),
        featureCount: document.getElementById("feature-count"),
        playerCount: document.getElementById("player-count"),
        bankrollValue: document.getElementById("bankroll-value"),
        roiValue: document.getElementById("roi-value"),
        openBetsValue: document.getElementById("open-bets-value"),
        todayDate: document.getElementById("today-date"),
        todayBody: document.getElementById("today-body"),
        deepDiveSelect: document.getElementById("deep-dive-select"),
        deepDiveLoadBtn: document.getElementById("deep-dive-load-btn"),
        deepDiveOverview: document.getElementById("deep-dive-overview"),
        shapBody: document.getElementById("shap-body"),
        featureBody: document.getElementById("feature-body"),
        performanceBody: document.getElementById("performance-body"),
        betsBody: document.getElementById("bets-body"),
        auditBody: document.getElementById("audit-body"),
        summarySeason: document.getElementById("summary-season"),
        summaryTotalBets: document.getElementById("summary-total-bets"),
        summarySettledBets: document.getElementById("summary-settled-bets"),
        summaryTotalStake: document.getElementById("summary-total-stake"),
        summaryTotalPnl: document.getElementById("summary-total-pnl"),
        summaryBankroll: document.getElementById("summary-bankroll"),
        summaryRoi: document.getElementById("summary-roi"),
    };

    const state = {
        activeTab: "home",
        raw: {
            table: null,
            offset: 0,
            limit: 50,
            total: 0,
            season: CURRENT_SEASON,
        },
    };

    function fmtNum(value) {
        return Number(value || 0).toLocaleString();
    }

    function fmtMoney(value) {
        return `$${Number(value || 0).toFixed(2)}`;
    }

    function fmtPct(value, digits = 2) {
        return `${(Number(value || 0) * 100).toFixed(digits)}%`;
    }

    function fmtDateTime(value) {
        if (!value) return "--";
        return new Date(value).toLocaleString();
    }

    function fmtSecs(value) {
        if (value == null) return "--";
        return `${Number(value).toFixed(2)}s`;
    }

    function safeText(value) {
        if (value == null) return "—";
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
    }

    function tableMessage(tbody, colspan, message) {
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="empty">${message}</td></tr>`;
    }

    function statusTag(status) {
        if (status === "success" || status === "healthy" || status === "win") return "tag tag-success";
        if (status === "pending" || status === "open") return "tag tag-pending";
        return "tag tag-failed";
    }

    function setOverallStatus(type, message) {
        dom.overallStatus.textContent = message;
        dom.overallStatus.className = `pill pill-${type}`;
    }

    function pickConsensus(predictions) {
        if (!predictions || typeof predictions !== "object") return null;
        if (predictions.ensemble) return { model: "ensemble", payload: predictions.ensemble };
        const first = Object.entries(predictions)[0];
        if (!first) return null;
        return { model: first[0], payload: first[1] };
    }

    async function fetchJSON(path, options = {}) {
        const ctrl = new AbortController();
        const timeout = setTimeout(() => ctrl.abort(), 15000);
        try {
            const res = await fetch(`${API_BASE}${path}`, { ...options, signal: ctrl.signal });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return await res.json();
        } finally {
            clearTimeout(timeout);
        }
    }

    function switchTab(tabName) {
        state.activeTab = tabName;
        dom.tabButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tabName));
        dom.tabPanels.forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${tabName}`));
    }

    function applyTheme(theme) {
        const isDark = theme === "dark";
        document.body.classList.toggle("theme-dark", isDark);
        dom.themeToggleBtn.textContent = isDark ? "Light Mode" : "Dark Mode";
        dom.themeToggleBtn.setAttribute("aria-pressed", isDark ? "true" : "false");
    }

    function initTheme() {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored === "dark" || stored === "light") {
            applyTheme(stored);
            return;
        }
        const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
        applyTheme(prefersDark ? "dark" : "light");
    }

    function toggleTheme() {
        const next = document.body.classList.contains("theme-dark") ? "light" : "dark";
        localStorage.setItem(THEME_KEY, next);
        applyTheme(next);
    }

    async function loadRawTables() {
        try {
            const season = dom.rawSeasonInput.value.trim() || CURRENT_SEASON;
            state.raw.season = season;
            const data = await fetchJSON(`/raw/tables?season=${encodeURIComponent(season)}`);
            const tables = data.tables || [];

            if (!tables.length) {
                dom.rawTableSelect.innerHTML = `<option value="">No tables found</option>`;
                tableMessage(dom.rawBody, 1, "No raw tables available.");
                return;
            }

            dom.rawTableSelect.innerHTML = tables
                .map((t) => `<option value="${t.table}">${t.label} (${fmtNum(t.row_count)})</option>`)
                .join("");

            if (!state.raw.table || !tables.some((t) => t.table === state.raw.table)) {
                state.raw.table = tables[0].table;
            }
            dom.rawTableSelect.value = state.raw.table;
        } catch (err) {
            console.error("loadRawTables failed", err);
            dom.rawTableSelect.innerHTML = `<option value="">Unable to load tables</option>`;
            tableMessage(dom.rawBody, 1, "Could not load raw table metadata.");
        }
    }

    async function loadRawRows() {
        const tableName = dom.rawTableSelect.value;
        if (!tableName) return;

        state.raw.table = tableName;
        state.raw.limit = Math.min(300, Math.max(10, Number(dom.rawLimitInput.value || 50)));
        state.raw.season = dom.rawSeasonInput.value.trim() || CURRENT_SEASON;

        tableMessage(dom.rawBody, 1, `Loading ${tableName}...`);
        try {
            const qs = new URLSearchParams({
                limit: String(state.raw.limit),
                offset: String(state.raw.offset),
                season: state.raw.season,
            }).toString();

            const data = await fetchJSON(`/raw/${encodeURIComponent(tableName)}?${qs}`);
            const rows = data.rows || [];
            state.raw.total = Number(data.total || 0);

            if (!rows.length) {
                dom.rawHead.innerHTML = "";
                tableMessage(dom.rawBody, 1, "No rows available for this selection.");
            } else {
                const cols = Object.keys(rows[0]);
                dom.rawHead.innerHTML = `<tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr>`;
                dom.rawBody.innerHTML = rows
                    .map((row) => `<tr>${cols.map((c) => `<td>${safeText(row[c])}</td>`).join("")}</tr>`)
                    .join("");
            }

            const start = state.raw.total ? state.raw.offset + 1 : 0;
            const end = Math.min(state.raw.offset + rows.length, state.raw.total);
            dom.rawMeta.textContent = `Rows ${fmtNum(start)}-${fmtNum(end)} of ${fmtNum(state.raw.total)}`;
            dom.rawPrevBtn.disabled = state.raw.offset <= 0;
            dom.rawNextBtn.disabled = state.raw.offset + state.raw.limit >= state.raw.total;
        } catch (err) {
            console.error("loadRawRows failed", err);
            tableMessage(dom.rawBody, 1, "Could not load rows for selected table.");
        }
    }

    async function loadQualityOverview() {
        tableMessage(dom.qualityRunBody, 7, "Loading quality overview...");
        try {
            const season = dom.qualitySeasonInput.value.trim() || CURRENT_SEASON;
            const data = await fetchJSON(`/quality/overview?season=${encodeURIComponent(season)}&recent_limit=20`);

            dom.qMatches.textContent = fmtNum(data.row_counts?.matches);
            dom.qTeams.textContent = fmtNum(data.row_counts?.teams);
            dom.qPlayers.textContent = fmtNum(data.row_counts?.players);
            dom.qTeamStats.textContent = fmtNum(data.row_counts?.team_game_stats);
            dom.qPlayerStats.textContent = fmtNum(data.row_counts?.player_game_stats);
            dom.qAvgIngest.textContent = fmtSecs(data.pipeline_timing?.avg_ingestion_seconds);
            dom.qAvgFeature.textContent = fmtSecs(data.pipeline_timing?.avg_feature_seconds);
            dom.qLatestIngest.textContent = fmtSecs(data.pipeline_timing?.latest_ingestion_seconds);
            dom.qLatestFeature.textContent = fmtSecs(data.pipeline_timing?.latest_feature_seconds);

            const checks = data.quality_checks || {};
            const checkEntries = Object.entries(checks);
            if (!checkEntries.length) {
                tableMessage(dom.qualityCheckBody, 2, "No quality check payload available.");
            } else {
                dom.qualityCheckBody.innerHTML = checkEntries
                    .map(([k, v]) => `<tr><td>${k}</td><td class="mono">${safeText(v)}</td></tr>`)
                    .join("");
            }

            const topTeams = data.top_teams || [];
            if (!topTeams.length) {
                tableMessage(dom.qualityTeamBody, 4, "No team performance rows available.");
            } else {
                dom.qualityTeamBody.innerHTML = topTeams
                    .map(
                        (row) => `
                        <tr>
                            <td>${row.abbreviation}</td>
                            <td class="mono">${fmtNum(row.wins)}</td>
                            <td class="mono">${fmtNum(row.losses)}</td>
                            <td class="mono">${fmtPct(row.win_pct, 1)}</td>
                        </tr>
                    `
                    )
                    .join("");
            }

            const runs = data.recent_runs || [];
            if (!runs.length) {
                tableMessage(dom.qualityRunBody, 7, "No recent run history available.");
            } else {
                dom.qualityRunBody.innerHTML = runs
                    .map(
                        (run) => `
                        <tr>
                            <td class="mono">${fmtDateTime(run.sync_time)}</td>
                            <td><code>${run.module}</code></td>
                            <td><span class="${statusTag(run.status)}">${run.status}</span></td>
                            <td class="mono">${fmtNum(run.records_processed)}</td>
                            <td class="mono">${fmtNum(run.records_inserted)}</td>
                            <td class="mono">${run.elapsed_seconds == null ? "--" : Number(run.elapsed_seconds).toFixed(2)}</td>
                            <td>${run.errors || "—"}</td>
                        </tr>
                    `
                    )
                    .join("");
            }
        } catch (err) {
            console.error("loadQualityOverview failed", err);
            tableMessage(dom.qualityRunBody, 7, "Could not load quality overview.");
            tableMessage(dom.qualityCheckBody, 2, "Could not load quality checks.");
            tableMessage(dom.qualityTeamBody, 4, "Could not load top teams.");
        }
    }

    async function loadSystemStatus() {
        try {
            const data = await fetchJSON("/system/status");
            if (data.status === "healthy") setOverallStatus("healthy", "System Healthy");
            else if (data.status === "error") setOverallStatus("error", "System Error");
            else setOverallStatus("degraded", "System Degraded");

            dom.dbStatus.textContent = (data.database || "--").toUpperCase();
            dom.pipelineStatus.textContent = (data.pipeline?.last_status || "--").toUpperCase();
            dom.lastSync.textContent = `Last sync: ${fmtDateTime(data.pipeline?.last_sync)}`;
            dom.matchCount.textContent = fmtNum(data.stats?.matches);
            dom.featureCount.textContent = fmtNum(data.stats?.features);
            dom.playerCount.textContent = fmtNum(data.stats?.active_players);
            renderAudit(data.audit_history || []);
        } catch (err) {
            console.error("loadSystemStatus failed", err);
            setOverallStatus("error", "API Connection Error");
            tableMessage(dom.auditBody, 7, "Could not load audit history.");
        }
    }

    function renderAudit(rows) {
        if (!rows.length) {
            tableMessage(dom.auditBody, 7, "No pipeline audit rows found yet.");
            return;
        }
        dom.auditBody.innerHTML = rows
            .map((row) => {
                const elapsed = row.details?.elapsed_seconds ? `${Number(row.details.elapsed_seconds).toFixed(1)}s` : "--";
                return `
                    <tr>
                        <td class="mono">${fmtDateTime(row.sync_time)}</td>
                        <td><code>${row.module}</code></td>
                        <td><span class="${statusTag(row.status)}">${row.status}</span></td>
                        <td class="mono">${fmtNum(row.processed ?? row.records_processed)}</td>
                        <td class="mono">${fmtNum(row.inserted ?? row.records_inserted)}</td>
                        <td class="mono">${elapsed}</td>
                        <td>${row.errors || "—"}</td>
                    </tr>
                `;
            })
            .join("");
    }

    async function loadTodayPredictions() {
        tableMessage(dom.todayBody, 5, "Loading today's predictions...");
        try {
            const data = await fetchJSON("/predictions/today?persist=false");
            dom.todayDate.textContent = `Date: ${data.date || "--"} · Games: ${data.count || 0}`;
            if (!data.games || !data.games.length) {
                tableMessage(dom.todayBody, 5, "No scheduled games for today.");
                return;
            }
            dom.todayBody.innerHTML = data.games
                .map((game) => {
                    const consensus = pickConsensus(game.predictions);
                    return `
                        <tr>
                            <td class="mono">${game.game_id}</td>
                            <td>${game.away_team} @ ${game.home_team}</td>
                            <td>${consensus ? `${consensus.model}: ${consensus.payload?.prediction || "--"}` : "--"}</td>
                            <td class="mono">${fmtPct(consensus?.payload?.home_win_prob)}</td>
                            <td class="mono">${fmtPct(consensus?.payload?.confidence)}</td>
                        </tr>
                    `;
                })
                .join("");
        } catch (err) {
            console.error("loadTodayPredictions failed", err);
            tableMessage(dom.todayBody, 5, "Could not load today's predictions.");
        }
    }

    async function loadDeepDiveOptions() {
        try {
            const data = await fetchJSON(`/matches?season=${encodeURIComponent(CURRENT_SEASON)}&limit=30`);
            const matches = data.matches || [];
            if (!matches.length) {
                dom.deepDiveSelect.innerHTML = `<option value="">No recent games available</option>`;
                return;
            }
            dom.deepDiveSelect.innerHTML = matches
                .map((m) => `<option value="${m.game_id}">${m.game_date} · ${m.away_team} @ ${m.home_team} (${m.game_id})</option>`)
                .join("");
        } catch (err) {
            console.error("loadDeepDiveOptions failed", err);
            dom.deepDiveSelect.innerHTML = `<option value="">Could not load match list</option>`;
        }
    }

    async function loadDeepDiveForGame(gameId) {
        if (!gameId) {
            dom.deepDiveOverview.textContent = "Select a game to inspect prediction details.";
            tableMessage(dom.shapBody, 3, "No explanation loaded.");
            tableMessage(dom.featureBody, 5, "No feature snapshot loaded.");
            return;
        }
        dom.deepDiveOverview.textContent = "Loading game details...";
        tableMessage(dom.shapBody, 3, "Loading SHAP factors...");
        tableMessage(dom.featureBody, 5, "Loading feature snapshot...");

        try {
            const [prediction, features] = await Promise.all([
                fetchJSON(`/predictions/game/${gameId}`),
                fetchJSON(`/features/${gameId}`),
            ]);
            const consensus = pickConsensus(prediction.predictions);
            dom.deepDiveOverview.innerHTML = `
                <strong>${prediction.away_team} @ ${prediction.home_team}</strong><br>
                Model: <code>${consensus?.model || "--"}</code> ·
                Home ${fmtPct(consensus?.payload?.home_win_prob)} / Away ${fmtPct(consensus?.payload?.away_win_prob)} ·
                Confidence ${fmtPct(consensus?.payload?.confidence)}
            `;

            const factors = prediction.explanation?.top_factors || [];
            if (!factors.length) tableMessage(dom.shapBody, 3, "No SHAP factors returned for this game.");
            else {
                dom.shapBody.innerHTML = factors
                    .map(
                        (factor) => `
                        <tr>
                            <td>${factor.display_name || factor.feature}</td>
                            <td class="mono">${Number(factor.impact || 0).toFixed(4)}</td>
                            <td>${factor.direction === "favors_home" ? "Favors Home" : "Favors Away"}</td>
                        </tr>
                    `
                    )
                    .join("");
            }

            const rows = features.features || [];
            if (!rows.length) tableMessage(dom.featureBody, 5, "No feature rows found for this game.");
            else {
                dom.featureBody.innerHTML = rows
                    .map(
                        (row) => `
                        <tr>
                            <td>${row.abbreviation || "--"}</td>
                            <td class="mono">${Number(row.win_pct_last_5 || 0).toFixed(3)}</td>
                            <td class="mono">${Number(row.avg_point_diff_last_5 || 0).toFixed(2)}</td>
                            <td class="mono">${row.days_rest ?? "--"}</td>
                            <td class="mono">${row.current_streak ?? "--"}</td>
                        </tr>
                    `
                    )
                    .join("");
            }
        } catch (err) {
            console.error("loadDeepDiveForGame failed", err);
            dom.deepDiveOverview.textContent = "Could not load deep dive for this game.";
            tableMessage(dom.shapBody, 3, "Deep dive unavailable.");
            tableMessage(dom.featureBody, 5, "Deep dive unavailable.");
        }
    }

    async function loadPerformance() {
        tableMessage(dom.performanceBody, 5, "Loading model performance...");
        try {
            const data = await fetchJSON(`/predictions/performance?season=${encodeURIComponent(CURRENT_SEASON)}`);
            const rows = data.performance || [];
            if (!rows.length) {
                tableMessage(dom.performanceBody, 5, "No evaluated model rows yet.");
                return;
            }
            dom.performanceBody.innerHTML = rows
                .map(
                    (row) => `
                    <tr>
                        <td><code>${row.model_name}</code></td>
                        <td class="mono">${fmtNum(row.evaluated_games)}</td>
                        <td class="mono">${fmtPct(row.accuracy)}</td>
                        <td class="mono">${Number(row.brier_score || 0).toFixed(4)}</td>
                        <td class="mono">${fmtPct(row.avg_confidence)}</td>
                    </tr>
                `
                )
                .join("");
        } catch (err) {
            console.error("loadPerformance failed", err);
            tableMessage(dom.performanceBody, 5, "Could not load model performance.");
        }
    }

    async function loadBankroll() {
        tableMessage(dom.betsBody, 6, "Loading bets...");
        try {
            const [summaryResp, betsResp] = await Promise.all([
                fetchJSON(`/bets/summary?season=${encodeURIComponent(CURRENT_SEASON)}`),
                fetchJSON(`/bets?season=${encodeURIComponent(CURRENT_SEASON)}&limit=10`),
            ]);
            const summary = summaryResp.summary || {};
            dom.summarySeason.textContent = summary.season || CURRENT_SEASON;
            dom.summaryTotalBets.textContent = fmtNum(summary.total_bets);
            dom.summarySettledBets.textContent = fmtNum(summary.settled_bets);
            dom.summaryTotalStake.textContent = fmtMoney(summary.total_stake);
            dom.summaryTotalPnl.textContent = fmtMoney(summary.total_pnl);
            dom.summaryBankroll.textContent = fmtMoney(summary.current_bankroll);
            dom.summaryRoi.textContent = fmtPct(summary.roi);
            dom.bankrollValue.textContent = fmtMoney(summary.current_bankroll);
            dom.roiValue.textContent = fmtPct(summary.roi);
            dom.openBetsValue.textContent = fmtNum(summary.open_bets);

            const rows = betsResp.bets || [];
            if (!rows.length) {
                tableMessage(dom.betsBody, 6, "No bets logged yet.");
                return;
            }
            dom.betsBody.innerHTML = rows
                .map(
                    (bet) => `
                    <tr>
                        <td class="mono">${bet.id}</td>
                        <td>${bet.away_team || "--"} @ ${bet.home_team || "--"}</td>
                        <td>${bet.selection}</td>
                        <td class="mono">${fmtMoney(bet.stake)}</td>
                        <td><span class="${statusTag(bet.result || "pending")}">${bet.result || "pending"}</span></td>
                        <td class="mono">${bet.pnl == null ? "--" : fmtMoney(bet.pnl)}</td>
                    </tr>
                `
                )
                .join("");
        } catch (err) {
            console.error("loadBankroll failed", err);
            tableMessage(dom.betsBody, 6, "Could not load bankroll data.");
        }
    }

    async function refreshAll() {
        dom.refreshAllBtn.disabled = true;
        dom.refreshAllBtn.textContent = "Refreshing...";
        await Promise.all([
            loadRawTables().then(loadRawRows),
            loadQualityOverview(),
            loadSystemStatus(),
            loadTodayPredictions(),
            loadPerformance(),
            loadBankroll(),
            loadDeepDiveOptions(),
        ]);
        if (dom.deepDiveSelect.value) await loadDeepDiveForGame(dom.deepDiveSelect.value);
        dom.refreshAllBtn.disabled = false;
        dom.refreshAllBtn.textContent = "Refresh";
    }

    dom.tabButtons.forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));
    dom.themeToggleBtn.addEventListener("click", toggleTheme);
    dom.refreshAllBtn.addEventListener("click", refreshAll);

    dom.rawRefreshBtn.addEventListener("click", async () => {
        state.raw.offset = 0;
        await loadRawTables();
        await loadRawRows();
    });
    dom.rawLoadBtn.addEventListener("click", async () => {
        state.raw.offset = 0;
        await loadRawRows();
    });
    dom.rawTableSelect.addEventListener("change", async () => {
        state.raw.offset = 0;
        await loadRawRows();
    });
    dom.rawPrevBtn.addEventListener("click", async () => {
        state.raw.offset = Math.max(0, state.raw.offset - state.raw.limit);
        await loadRawRows();
    });
    dom.rawNextBtn.addEventListener("click", async () => {
        state.raw.offset += state.raw.limit;
        await loadRawRows();
    });

    dom.qualityRefreshBtn.addEventListener("click", loadQualityOverview);
    dom.qualityLoadBtn.addEventListener("click", loadQualityOverview);

    dom.refreshTodayBtn.addEventListener("click", loadTodayPredictions);
    dom.refreshAuditBtn.addEventListener("click", loadSystemStatus);
    dom.refreshBankrollBtn.addEventListener("click", loadBankroll);
    dom.deepDiveLoadBtn.addEventListener("click", () => loadDeepDiveForGame(dom.deepDiveSelect.value));
    dom.deepDiveSelect.addEventListener("change", () => loadDeepDiveForGame(dom.deepDiveSelect.value));

    initTheme();
    switchTab("home");
    refreshAll();

    setInterval(() => {
        loadSystemStatus();
        loadQualityOverview();
        if (state.activeTab === "analysis") {
            loadTodayPredictions();
            loadPerformance();
            loadBankroll();
        }
    }, 60000);
});
