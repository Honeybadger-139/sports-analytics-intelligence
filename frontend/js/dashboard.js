document.addEventListener("DOMContentLoaded", () => {
    const API_BASE = "/api/v1";
    const CURRENT_SEASON = "2025-26";

    const dom = {
        overallStatus: document.getElementById("overall-status"),
        refreshAllBtn: document.getElementById("refresh-all-btn"),
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

    function tableMessage(tbody, colspan, message) {
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="empty">${message}</td></tr>`;
    }

    function statusTag(status) {
        if (status === "success" || status === "healthy" || status === "win") {
            return "tag tag-success";
        }
        if (status === "pending" || status === "open") {
            return "tag tag-pending";
        }
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
        const timeout = setTimeout(() => ctrl.abort(), 12000);
        try {
            const res = await fetch(`${API_BASE}${path}`, { ...options, signal: ctrl.signal });
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            return await res.json();
        } finally {
            clearTimeout(timeout);
        }
    }

    async function loadSystemStatus() {
        try {
            const data = await fetchJSON("/system/status");
            if (data.status === "healthy") {
                setOverallStatus("healthy", "System Healthy");
            } else if (data.status === "error") {
                setOverallStatus("error", "System Error");
            } else {
                setOverallStatus("degraded", "System Degraded");
            }

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
        dom.auditBody.innerHTML = rows.map((row) => {
            const elapsed = row.details?.elapsed_seconds ? `${Number(row.details.elapsed_seconds).toFixed(1)}s` : "--";
            const stateClass = statusTag(row.status);
            return `
                <tr>
                    <td class="mono">${fmtDateTime(row.sync_time)}</td>
                    <td><code>${row.module}</code></td>
                    <td><span class="${stateClass}">${row.status}</span></td>
                    <td class="mono">${fmtNum(row.processed ?? row.records_processed)}</td>
                    <td class="mono">${fmtNum(row.inserted ?? row.records_inserted)}</td>
                    <td class="mono">${elapsed}</td>
                    <td>${row.errors || "—"}</td>
                </tr>
            `;
        }).join("");
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

            dom.todayBody.innerHTML = data.games.map((game) => {
                const consensus = pickConsensus(game.predictions);
                const homeProb = consensus?.payload?.home_win_prob ?? 0;
                const confidence = consensus?.payload?.confidence ?? 0;
                const side = consensus?.payload?.prediction || "--";
                return `
                    <tr>
                        <td class="mono">${game.game_id}</td>
                        <td>${game.away_team} @ ${game.home_team}</td>
                        <td>${consensus ? `${consensus.model}: ${side}` : "--"}</td>
                        <td class="mono">${fmtPct(homeProb)}</td>
                        <td class="mono">${fmtPct(confidence)}</td>
                    </tr>
                `;
            }).join("");
        } catch (err) {
            console.error("loadTodayPredictions failed", err);
            tableMessage(dom.todayBody, 5, "Could not load today's predictions.");
        }
    }

    async function loadDeepDiveOptions() {
        try {
            const data = await fetchJSON(`/matches?season=${CURRENT_SEASON}&limit=30`);
            const matches = data.matches || [];
            if (!matches.length) {
                dom.deepDiveSelect.innerHTML = `<option value="">No recent games available</option>`;
                return;
            }

            dom.deepDiveSelect.innerHTML = matches.map((m) => {
                const label = `${m.game_date} · ${m.away_team} @ ${m.home_team} (${m.game_id})`;
                return `<option value="${m.game_id}">${label}</option>`;
            }).join("");
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
            const homeProb = consensus?.payload?.home_win_prob ?? 0;
            const awayProb = consensus?.payload?.away_win_prob ?? 0;

            dom.deepDiveOverview.innerHTML = `
                <strong>${prediction.away_team} @ ${prediction.home_team}</strong><br>
                Model: <code>${consensus?.model || "--"}</code> · 
                Home ${fmtPct(homeProb)} / Away ${fmtPct(awayProb)} ·
                Confidence ${fmtPct(consensus?.payload?.confidence ?? 0)}
            `;

            const factors = prediction.explanation?.top_factors || [];
            if (!factors.length) {
                tableMessage(dom.shapBody, 3, "No SHAP factors returned for this game.");
            } else {
                dom.shapBody.innerHTML = factors.map((factor) => `
                    <tr>
                        <td>${factor.display_name || factor.feature}</td>
                        <td class="mono">${Number(factor.impact || 0).toFixed(4)}</td>
                        <td>${factor.direction === "favors_home" ? "Favors Home" : "Favors Away"}</td>
                    </tr>
                `).join("");
            }

            const rows = features.features || [];
            if (!rows.length) {
                tableMessage(dom.featureBody, 5, "No feature rows found for this game.");
            } else {
                dom.featureBody.innerHTML = rows.map((row) => `
                    <tr>
                        <td>${row.abbreviation || "--"}</td>
                        <td class="mono">${Number(row.win_pct_last_5 || 0).toFixed(3)}</td>
                        <td class="mono">${Number(row.avg_point_diff_last_5 || 0).toFixed(2)}</td>
                        <td class="mono">${row.days_rest ?? "--"}</td>
                        <td class="mono">${row.current_streak ?? "--"}</td>
                    </tr>
                `).join("");
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
            const data = await fetchJSON(`/predictions/performance?season=${CURRENT_SEASON}`);
            const rows = data.performance || [];
            if (!rows.length) {
                tableMessage(dom.performanceBody, 5, "No evaluated model rows yet.");
                return;
            }

            dom.performanceBody.innerHTML = rows.map((row) => `
                <tr>
                    <td><code>${row.model_name}</code></td>
                    <td class="mono">${fmtNum(row.evaluated_games)}</td>
                    <td class="mono">${fmtPct(row.accuracy)}</td>
                    <td class="mono">${Number(row.brier_score || 0).toFixed(4)}</td>
                    <td class="mono">${fmtPct(row.avg_confidence)}</td>
                </tr>
            `).join("");
        } catch (err) {
            console.error("loadPerformance failed", err);
            tableMessage(dom.performanceBody, 5, "Could not load model performance.");
        }
    }

    async function loadBankroll() {
        tableMessage(dom.betsBody, 6, "Loading bets...");
        try {
            const [summaryResp, betsResp] = await Promise.all([
                fetchJSON(`/bets/summary?season=${CURRENT_SEASON}`),
                fetchJSON(`/bets?season=${CURRENT_SEASON}&limit=10`),
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

            dom.betsBody.innerHTML = rows.map((bet) => `
                <tr>
                    <td class="mono">${bet.id}</td>
                    <td>${bet.away_team || "--"} @ ${bet.home_team || "--"}</td>
                    <td>${bet.selection}</td>
                    <td class="mono">${fmtMoney(bet.stake)}</td>
                    <td><span class="${statusTag(bet.result || "pending")}">${bet.result || "pending"}</span></td>
                    <td class="mono">${bet.pnl == null ? "--" : fmtMoney(bet.pnl)}</td>
                </tr>
            `).join("");
        } catch (err) {
            console.error("loadBankroll failed", err);
            tableMessage(dom.betsBody, 6, "Could not load bankroll data.");
        }
    }

    async function refreshAll() {
        dom.refreshAllBtn.disabled = true;
        dom.refreshAllBtn.textContent = "Refreshing...";
        await Promise.all([
            loadSystemStatus(),
            loadTodayPredictions(),
            loadPerformance(),
            loadBankroll(),
            loadDeepDiveOptions(),
        ]);

        if (dom.deepDiveSelect.value) {
            await loadDeepDiveForGame(dom.deepDiveSelect.value);
        }

        dom.refreshAllBtn.disabled = false;
        dom.refreshAllBtn.textContent = "Refresh All";
    }

    dom.refreshAllBtn.addEventListener("click", refreshAll);
    dom.refreshTodayBtn.addEventListener("click", loadTodayPredictions);
    dom.refreshAuditBtn.addEventListener("click", loadSystemStatus);
    dom.refreshBankrollBtn.addEventListener("click", loadBankroll);
    dom.deepDiveLoadBtn.addEventListener("click", () => loadDeepDiveForGame(dom.deepDiveSelect.value));
    dom.deepDiveSelect.addEventListener("change", () => loadDeepDiveForGame(dom.deepDiveSelect.value));

    refreshAll();
    setInterval(() => {
        loadSystemStatus();
        loadTodayPredictions();
        loadPerformance();
        loadBankroll();
    }, 45000);
});
