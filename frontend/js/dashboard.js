document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = '/api/v1';

    // DOM Elements
    const overallStatus = document.getElementById('overall-status');
    const dbStatus = document.getElementById('db-status');
    const pipelineStatus = document.getElementById('pipeline-status');
    const lastSync = document.getElementById('last-sync');
    const matchCount = document.getElementById('match-count');
    const featureCount = document.getElementById('feature-count');
    const auditBody = document.getElementById('audit-body');
    const refreshBtn = document.getElementById('refresh-btn');

    async function fetchStatus() {
        try {
            const response = await fetch(`${API_BASE}/system/status`);
            const data = await response.json();

            if (data.status === 'healthy') {
                overallStatus.textContent = 'System Healthy';
                overallStatus.className = 'status-badge status-healthy';
            } else {
                overallStatus.textContent = 'System Degraded';
                overallStatus.className = 'status-badge status-degraded';
            }

            // Cards
            dbStatus.textContent = data.database.toUpperCase();
            dbStatus.style.color = data.database === 'online' ? 'var(--success-color)' : 'var(--error-color)';

            pipelineStatus.textContent = data.pipeline.last_status.toUpperCase();
            pipelineStatus.style.color = data.pipeline.last_status === 'success' ? 'var(--success-color)' : 'var(--error-color)';

            lastSync.textContent = `Last Sync: ${data.pipeline.last_sync ? new Date(data.pipeline.last_sync).toLocaleString() : 'Never'}`;
            matchCount.textContent = data.stats.matches.toLocaleString();
            featureCount.textContent = data.stats.features.toLocaleString();

            // Table
            renderAudit(data.audit_history);

        } catch (error) {
            console.error('Failed to fetch status:', error);
            overallStatus.textContent = 'Connection Error';
            overallStatus.className = 'status-badge status-error';
        }
    }

    function renderAudit(logs) {
        if (!logs || logs.length === 0) {
            auditBody.innerHTML = '<tr><td colspan="6" class="loading">No history found.</td></tr>';
            return;
        }

        auditBody.innerHTML = logs.map(log => {
            const date = new Date(log.sync_time).toLocaleString();
            const statusClass = log.status === 'success' ? 'tag-success' : 'tag-failed';
            const elapsed = log.details?.elapsed_seconds ? `${log.details.elapsed_seconds}s` : 'N/A';

            return `
                <tr>
                    <td>${date}</td>
                    <td><code>${log.module}</code></td>
                    <td><span class="tag ${statusClass}">${log.status}</span></td>
                    <td>${log.processed}</td>
                    <td>${elapsed}</td>
                    <td><small style="color: var(--error-color)">${log.errors || '-'}</small></td>
                </tr>
            `;
        }).join('');
    }

    refreshBtn.addEventListener('click', fetchStatus);

    // Initial load
    fetchStatus();

    // Auto-refresh every 30 seconds
    setInterval(fetchStatus, 30000);
});
