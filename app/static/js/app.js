let currentTab = 'dashboard';
let drives = [];
let sortedDrives = [];
let currentDriveIndex = -1;
let historyChart = null;
let modalChart = null;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initButtons();
    loadDrives();
    loadConfig();
});

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

            tab.classList.add('active');
            const tabId = tab.dataset.tab;
            document.getElementById(tabId).classList.add('active');
            currentTab = tabId;

            if (tabId === 'drives') {
                renderDrivesTable();
            }
        });
    });
}

function initButtons() {
    document.getElementById('populateBtn').addEventListener('click', populateDrives);
    document.getElementById('collectBtn').addEventListener('click', manualCollect);
    document.getElementById('refreshBtn').addEventListener('click', loadDrives);
    document.getElementById('saveSettings').addEventListener('click', saveSettings);
    document.getElementById('loadHistory').addEventListener('click', loadHistoryChart);

    document.querySelector('.close').addEventListener('click', closeModal);
    document.getElementById('driveModal').addEventListener('click', (e) => {
        if (e.target === document.getElementById('driveModal')) {
            closeModal();
        }
    });
}

async function loadDrives() {
    try {
        const response = await fetch('/api/drives');
        drives = await response.json();
        renderDashboard();
        updateHistoryDriveSelect();
    } catch (error) {
        console.error('Error loading drives:', error);
    }
}

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        if (config.collection_interval) {
            document.getElementById('collectionInterval').value = config.collection_interval;
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

async function saveSettings() {
    const interval = document.getElementById('collectionInterval').value;
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ collection_interval: interval })
        });
        alert('Settings saved successfully');
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Error saving settings');
    }
}

async function populateDrives() {
    const btn = document.getElementById('populateBtn');
    btn.disabled = true;
    btn.textContent = 'Populating...';

    try {
        const response = await fetch('/api/populate', { method: 'POST' });
        const result = await response.json();
        alert(result.message || 'Drives populated');
        await loadDrives();
    } catch (error) {
        console.error('Error populating drives:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Populate Drives';
    }
}

async function manualCollect() {
    const btn = document.getElementById('collectBtn');
    btn.disabled = true;
    btn.textContent = 'Running...';

    try {
        await fetch('/api/collect', { method: 'POST' });
        await loadDrives();
    } catch (error) {
        console.error('Error collecting data:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run SMART';
    }
}

function parseSizeToBytes(sizeStr) {
    if (!sizeStr || sizeStr === 'Unknown') return 0;
    const match = sizeStr.match(/([\d.]+)\s*(B|KB|MB|GB|TB|PB)/i);
    if (!match) return 0;
    const value = parseFloat(match[1]);
    const unit = match[2].toUpperCase();
    const units = { B: 1, KB: 1024, MB: 1024**2, GB: 1024**3, TB: 1024**4, PB: 1024**5 };
    return value * (units[unit] || 0);
}

function sortDrives() {
    sortedDrives = [...drives].sort((a, b) => {
        if (a.excluded !== b.excluded) return a.excluded ? 1 : -1;
        return parseSizeToBytes(b.size) - parseSizeToBytes(a.size);
    });
}

function renderDashboard() {
    const grid = document.getElementById('driveGrid');
    sortDrives();

    if (drives.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <h3>No drives found</h3>
                <p>Click "Run SMART" to scan for drives</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = sortedDrives.map(drive => `
        <div class="drive-card" onclick="openDriveModal('${drive.serial}')">
            <div class="drive-card-header">
                <h3>${drive.model || 'Unknown Drive'}</h3>
                <span class="drive-type-badge">${drive.drive_type || 'Unknown'}</span>
                <span class="status-badge ${getDriveStatus(drive)}">${getDriveStatusText(drive)}</span>
            </div>
            <div class="drive-stats">
                <div class="stat-item">
                    <span class="stat-label">Serial</span>
                    <span class="stat-value">${drive.serial}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Size</span>
                    <span class="stat-value">${drive.size || 'Unknown'}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Path</span>
                    <span class="stat-value">${drive.path}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Last Seen</span>
                    <span class="stat-value">${formatDate(drive.last_seen)}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function getDriveStatus(drive) {
    if (drive.excluded) return 'status-warning';
    return 'status-good';
}

function getDriveStatusText(drive) {
    if (drive.excluded) return 'Excluded';
    return 'Included';
}

function renderDrivesTable() {
    const tbody = document.getElementById('drivesTableBody');

    if (drives.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    No drives found. Click "Run SMART" to scan for drives.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = drives.map(drive => `
        <tr class="${drive.excluded ? 'excluded' : ''}">
            <td>${drive.serial}</td>
            <td>${drive.model || 'Unknown'}</td>
            <td>${drive.drive_type || 'Unknown'}</td>
            <td>${drive.path}</td>
            <td>${drive.size || 'Unknown'}</td>
            <td>${formatDate(drive.last_seen)}</td>
            <td>
                <span class="status-badge ${getDriveStatus(drive)}">
                    ${drive.excluded ? 'Excluded' : 'Included'}
                </span>
            </td>
            <td>
                <button class="btn btn-small ${drive.excluded ? 'btn-success' : 'btn-danger'}"
                        onclick="toggleExclude('${drive.serial}', ${!drive.excluded})">
                    ${drive.excluded ? 'Include' : 'Exclude'}
                </button>
            </td>
        </tr>
    `).join('');
}

async function toggleExclude(serial, exclude) {
    try {
        await fetch(`/api/drives/${serial}/exclude?exclude=${exclude}`, {
            method: 'POST'
        });
        await loadDrives();
        renderDrivesTable();
    } catch (error) {
        console.error('Error toggling drive exclusion:', error);
    }
}

async function openDriveModal(serial) {
    sortDrives();
    currentDriveIndex = sortedDrives.findIndex(d => d.serial === serial);
    updateModalNavButtons();
    await loadDriveModalData(serial);
}

async function loadDriveModalData(serial) {
    const modal = document.getElementById('driveModal');
    const title = document.getElementById('modalTitle');
    const statsContainer = document.getElementById('modalStats');

    const drive = drives.find(d => d.serial === serial);
    const driveName = drive ? (drive.model || 'Unknown Drive') : 'Unknown Drive';
    title.textContent = `${driveName} - ${serial}`;

    try {
        const response = await fetch(`/api/drives/${serial}/history?limit=50`);
        const history = await response.json();

        if (history.length > 0) {
            const latest = history[0].data;
            const previous = history.length > 1 ? history[1].data : null;

            renderModalChart(history);
            renderModalStats(statsContainer, latest, previous);
        } else {
            statsContainer.innerHTML = '<p>No data available for this drive</p>';
        }

        modal.classList.remove('hidden');
    } catch (error) {
        console.error('Error loading drive history:', error);
    }
}

function closeModal() {
    document.getElementById('driveModal').classList.add('hidden');
    currentDriveIndex = -1;
    if (modalChart) {
        modalChart.destroy();
        modalChart = null;
    }
}

function navigateDrive(direction) {
    if (sortedDrives.length === 0) return;
    currentDriveIndex += direction;
    if (currentDriveIndex < 0) currentDriveIndex = sortedDrives.length - 1;
    if (currentDriveIndex >= sortedDrives.length) currentDriveIndex = 0;
    if (modalChart) {
        modalChart.destroy();
        modalChart = null;
    }
    updateModalNavButtons();
    loadDriveModalData(sortedDrives[currentDriveIndex].serial);
}

function updateModalNavButtons() {
    const prevBtn = document.getElementById('modalPrevBtn');
    const nextBtn = document.getElementById('modalNextBtn');
    if (prevBtn && nextBtn) {
        prevBtn.disabled = sortedDrives.length <= 1;
        nextBtn.disabled = sortedDrives.length <= 1;
    }
}

function renderModalChart(history) {
    const ctx = document.getElementById('modalChart').getContext('2d');

    if (modalChart) {
        modalChart.destroy();
    }

    const labels = history.reverse().map(h => formatDate(h.timestamp));
    const temperatures = history.map(h => h.data.temperature);
    const powerOnHours = history.map(h => h.data.power_on_hours);
    const pendingSectors = history.map(h => h.data.current_pending_sector || 0);

    modalChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Temperature (°C)',
                    data: temperatures,
                    borderColor: 'rgb(255, 99, 132)',
                    tension: 0.1,
                    yAxisID: 'y'
                },
                {
                    label: 'Power On Hours',
                    data: powerOnHours,
                    borderColor: 'rgb(54, 162, 235)',
                    tension: 0.1,
                    yAxisID: 'y1'
                },
                {
                    label: 'Pending Sectors',
                    data: pendingSectors,
                    borderColor: 'rgb(255, 205, 86)',
                    tension: 0.1,
                    yAxisID: 'y'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: {
                        drawOnChartArea: false,
                    },
                },
            }
        }
    });
}

function renderModalStats(container, latest, previous) {
    const stats = [
        { label: 'Temperature', key: 'temperature', value: latest.temperature, unit: '°C' },
        { label: 'Power On Hours', key: 'power_on_hours', value: latest.power_on_hours, unit: 'hours' },
        { label: 'Power Cycle Count', key: 'power_cycle_count', value: latest.power_cycle_count, unit: '' },
        { label: 'Load Cycle Count', key: 'load_cycle_count', value: latest.load_cycle_count, unit: '' },
        { label: 'Reallocated Sectors', key: 'reallocated_sectors', value: latest.reallocated_sectors || 0, unit: '' },
        { label: 'Pending Sectors', key: 'current_pending_sector', value: latest.current_pending_sector || 0, unit: '' },
        { label: 'Uncorrectable Errors', key: 'reported_uncorrectable', value: latest.reported_uncorrectable || 0, unit: '' },
        { label: 'Hardware ECC Recovered', key: 'hardware_ecc_recovered', value: latest.hardware_ecc_recovered || 0, unit: '' },
        { label: 'End-to-End Errors', key: 'end_to_end_error', value: latest.end_to_end_error || 0, unit: '' },
        { label: 'CRC Errors', key: 'udma_crc_error_count', value: latest.udma_crc_error_count || 0, unit: '' },
    ];

    container.innerHTML = stats.map(stat => {
        let delta = '';
        if (previous && stat.value !== null && previous[stat.key] !== undefined) {
            const diff = stat.value - previous[stat.key];
            if (diff > 0) delta = `<span class="delta positive">+${diff}</span>`;
            else if (diff < 0) delta = `<span class="delta negative">${diff}</span>`;
        }

        return `
            <div class="stat-item">
                <span class="stat-label">${stat.label}</span>
                <span class="stat-value">${stat.value ?? 'N/A'} ${stat.unit} ${delta}</span>
            </div>
        `;
    }).join('');
}

function updateHistoryDriveSelect() {
    const select = document.getElementById('historyDrive');
    select.innerHTML = drives.map(drive =>
        `<option value="${drive.serial}">${drive.model || 'Unknown'} (${drive.serial})</option>`
    ).join('');
}

async function loadHistoryChart() {
    const serial = document.getElementById('historyDrive').value;
    if (!serial) return;

    try {
        const response = await fetch(`/api/drives/${serial}/history?limit=100`);
        const history = await response.json();

        const ctx = document.getElementById('historyChart').getContext('2d');

        if (historyChart) {
            historyChart.destroy();
        }

        const labels = history.reverse().map(h => formatDate(h.timestamp));
        const temperatures = history.map(h => h.data.temperature);
        const pendingSectors = history.map(h => h.data.current_pending_sector || 0);
        const reallocatedSectors = history.map(h => h.data.reallocated_sectors || 0);

        historyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Temperature (°C)',
                        data: temperatures,
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    },
                    {
                        label: 'Pending Sectors',
                        data: pendingSectors,
                        borderColor: 'rgb(255, 205, 86)',
                        tension: 0.1
                    },
                    {
                        label: 'Reallocated Sectors',
                        data: reallocatedSectors,
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}