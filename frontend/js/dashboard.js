document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = '/api/v1';

    // DOM Elements
    const overallStatus = document.getElementById('overall-status');
    const dbStatus = document.getElementById('db-status');
    const pipelineStatus = document.getElementById('pipeline-status');
    const lastSync = document.getElementById('last-sync');
    const matchCount = document.getElementById('match-count');
    const featureCount = document.getElementById('feature-count');
    const playerCount = document.getElementById('player-count');
    const auditBody = document.getElementById('audit-body');
    const refreshBtn = document.getElementById('refresh-btn');

    /**
     * Fetch system status from the API and update all dashboard cards.
     */
    async function fetchStatus() {
        try {
            overallStatus.textContent = 'Refreshing...';
            overallStatus.className = 'status-badge status-loading';

            const response = await fetch(`${API_BASE}/system/status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();

            // Overall status
            if (data.status === 'healthy') {
                overallStatus.textContent = '● System Healthy';
                overallStatus.className = 'status-badge status-healthy';
            } else if (data.status === 'error') {
                overallStatus.textContent = '✕ System Error';
                overallStatus.className = 'status-badge status-error';
            } else {
                overallStatus.textContent = '⚠ Degraded';
                overallStatus.className = 'status-badge status-degraded';
            }

            // Database card
            dbStatus.textContent = data.database.toUpperCase();
            dbStatus.style.color = data.database === 'online'
                ? 'var(--success-color)'
                : 'var(--error-color)';

            // Pipeline card
            const pipeStatus = data.pipeline?.last_status || 'unknown';
            pipelineStatus.textContent = pipeStatus.toUpperCase();
            pipelineStatus.style.color = pipeStatus === 'success'
                ? 'var(--success-color)'
                : pipeStatus === 'unknown'
                    ? 'var(--text-secondary)'
                    : 'var(--error-color)';

            lastSync.textContent = data.pipeline?.last_sync
                ? `Last Sync: ${new Date(data.pipeline.last_sync).toLocaleString()}`
                : 'Last Sync: Never';

            // Stats cards — animate the count-up
            animateValue(matchCount, parseInt(matchCount.textContent) || 0, data.stats?.matches || 0, 600);
            animateValue(featureCount, parseInt(featureCount.textContent) || 0, data.stats?.features || 0, 600);
            animateValue(playerCount, parseInt(playerCount.textContent) || 0, data.stats?.active_players || 0, 600);

            // Audit history table
            renderAudit(data.audit_history);

        } catch (error) {
            console.error('Failed to fetch status:', error);
            overallStatus.textContent = '✕ Connection Error';
            overallStatus.className = 'status-badge status-error';
            auditBody.innerHTML = `
                <tr><td colspan="7" class="loading">
                    Unable to reach API. Is the backend running?<br>
                    <small style="color: var(--text-muted)">Run <code>make run-api</code> from the backend/ directory</small>
                </td></tr>`;
        }
    }

    /**
     * Animate a numeric value from start to end.
     */
    function animateValue(element, start, end, duration) {
        if (start === end) { element.textContent = end.toLocaleString(); return; }
        const range = end - start;
        const startTime = performance.now();

        function step(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + range * eased);
            element.textContent = current.toLocaleString();
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    /**
     * Render audit logs into the history table.
     */
    function renderAudit(logs) {
        if (!logs || logs.length === 0) {
            auditBody.innerHTML = '<tr><td colspan="7" class="loading">No audit history found. Run <code>make ingest</code> to start.</td></tr>';
            return;
        }

        auditBody.innerHTML = logs.map(log => {
            const date = new Date(log.sync_time).toLocaleString();
            const statusClass = log.status === 'success' ? 'tag-success' : 'tag-failed';
            const elapsed = log.details?.elapsed_seconds
                ? `${log.details.elapsed_seconds.toFixed(1)}s`
                : 'N/A';
            const inserted = log.inserted ?? log.records_inserted ?? '-';

            return `
                <tr>
                    <td style="font-family: var(--font-mono); font-size: 0.78rem">${date}</td>
                    <td><code>${log.module}</code></td>
                    <td><span class="tag ${statusClass}">${log.status}</span></td>
                    <td>${(log.processed ?? log.records_processed ?? 0).toLocaleString()}</td>
                    <td>${typeof inserted === 'number' ? inserted.toLocaleString() : inserted}</td>
                    <td style="font-family: var(--font-mono)">${elapsed}</td>
                    <td><small style="color: var(--error-color)">${log.errors || '—'}</small></td>
                </tr>
            `;
        }).join('');
    }

    // Event listeners
    refreshBtn.addEventListener('click', () => {
        refreshBtn.textContent = '↻ Loading...';
        fetchStatus().then(() => {
            refreshBtn.textContent = '↻ Refresh';
        });
    });

    // Initial load
    fetchStatus();

    // Auto-refresh every 30 seconds
    setInterval(fetchStatus, 30000);
});
