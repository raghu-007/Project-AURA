/* ═══════════════════════════════════════════════════════════
   AURA — Ecosystem Intelligence Dashboard
   Real-time rendering, smooth animations, event-driven UX
   ═══════════════════════════════════════════════════════════ */

// ── Configuration ────────────────────────────────────────────

const WS_PORT = parseInt(window.location.port || '8765') + 1;
const WS_URL = `ws://${window.location.hostname}:${WS_PORT}`;
const RECONNECT_DELAY = 2000;
const CHART_HISTORY_LENGTH = 100;

// Entity colors
const COLORS = {
    GRASS_SEED: 'rgba(57, 217, 138, 0.15)',
    GRASS_SPROUT: 'rgba(57, 217, 138, 0.4)',
    GRASS_MATURE: '#39d98a',
    GRASS_DECAYING: 'rgba(57, 217, 138, 0.1)',
    BUSH_SEED: 'rgba(34, 197, 94, 0.15)',
    BUSH_SPROUT: 'rgba(34, 197, 94, 0.4)',
    BUSH_MATURE: '#22c55e',
    BUSH_DECAYING: 'rgba(34, 197, 94, 0.1)',
    TREE_SEED: 'rgba(21, 128, 61, 0.15)',
    TREE_SPROUT: 'rgba(21, 128, 61, 0.4)',
    TREE_MATURE: '#15803d',
    TREE_DECAYING: 'rgba(21, 128, 61, 0.1)',
    HERBIVORE: '#60a5fa',
    PREDATOR: '#ff6b6b',
    OMNIVORE: '#ffc145',
    BACKGROUND: '#0a0f16',
    GRID_LINE: 'rgba(80, 100, 130, 0.05)',
};

const SEASON_CONFIG = {
    Spring: { icon: '🌸', hue: 140, tint: 'rgba(57, 217, 138, 0.035)' },
    Summer: { icon: '☀️', hue: 40, tint: 'rgba(255, 193, 69, 0.03)' },
    Autumn: { icon: '🍂', hue: 25, tint: 'rgba(255, 140, 50, 0.03)' },
    Winter: { icon: '❄️', hue: 210, tint: 'rgba(91, 141, 239, 0.03)' },
};

const TIME_CONFIG = {
    DAWN: { icon: '🌅', dim: 0.15 },
    DAY: { icon: '☀️', dim: 0.0 },
    DUSK: { icon: '🌇', dim: 0.2 },
    NIGHT: { icon: '🌙', dim: 0.4 },
};

// ── State ────────────────────────────────────────────────────

let ws = null;
let cellSize = 8;
let worldWidth = 80;
let worldHeight = 60;
let lastState = null;
let previousEvents = [];
let animatingValues = {};

// ── DOM Elements ─────────────────────────────────────────────

const canvas = document.getElementById('worldCanvas');
const ctx = canvas.getContext('2d');
const connectionBadge = document.getElementById('connectionStatus');
const tickDisplay = document.getElementById('tickDisplay');
const toastContainer = document.getElementById('toastContainer');

const el = {
    floraCount: document.getElementById('floraCount'),
    herbCount: document.getElementById('herbCount'),
    predCount: document.getElementById('predCount'),
    omniCount: document.getElementById('omniCount'),
    biodiversity: document.getElementById('biodiversity'),
    avgEnergy: document.getElementById('avgEnergy'),
    totalBirths: document.getElementById('totalBirths'),
    totalDeaths: document.getElementById('totalDeaths'),
    seasonBadge: document.getElementById('seasonBadge'),
    seasonIcon: document.getElementById('seasonIcon'),
    seasonText: document.getElementById('seasonText'),
    timeBadge: document.getElementById('timeBadge'),
    timeIcon: document.getElementById('timeIcon'),
    timeText: document.getElementById('timeText'),
    eventBadge: document.getElementById('eventBadge'),
    eventText: document.getElementById('eventText'),
    traitSpeed: document.getElementById('traitSpeed'),
    traitVision: document.getElementById('traitVision'),
    traitSize: document.getElementById('traitSize'),
    traitSpeedVal: document.getElementById('traitSpeedVal'),
    traitVisionVal: document.getElementById('traitVisionVal'),
    traitSizeVal: document.getElementById('traitSizeVal'),
    bioArc: document.getElementById('bioArc'),
    energyArc: document.getElementById('energyArc'),
    popTrend: document.getElementById('popTrend'),
    entityInspector: document.getElementById('entityInspector'),
    inspectorIcon: document.getElementById('inspectorIcon'),
    inspectorTitle: document.getElementById('inspectorTitle'),
    inspectorBody: document.getElementById('inspectorBody'),
    inspectorClose: document.getElementById('inspectorClose'),
};

// ── Charts ───────────────────────────────────────────────────

const chartFont = { family: 'Inter', size: 10 };

const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400, easing: 'easeOutQuart' },
    plugins: {
        legend: {
            labels: { color: '#505a6a', font: chartFont, boxWidth: 10, padding: 12 },
        },
    },
    scales: {
        x: { display: false },
        y: {
            ticks: { color: '#3a4250', font: { ...chartFont, size: 9 }, maxTicksLimit: 5 },
            grid: { color: 'rgba(80,100,130,0.06)', drawBorder: false },
            border: { display: false },
        },
    },
    elements: {
        line: { borderWidth: 1.5, tension: 0.35 },
        point: { radius: 0 },
    },
};

const populationChart = new Chart(document.getElementById('populationChart'), {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            { label: 'Herbivores', data: [], borderColor: '#5b8def', backgroundColor: 'rgba(91,141,239,0.06)', fill: true },
            { label: 'Predators', data: [], borderColor: '#ff6b6b', backgroundColor: 'rgba(255,107,107,0.06)', fill: true },
            { label: 'Omnivores', data: [], borderColor: '#ffc145', backgroundColor: 'rgba(255,193,69,0.06)', fill: true },
        ],
    },
    options: { ...chartOpts },
});

const energyChart = new Chart(document.getElementById('energyChart'), {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            { label: 'Avg Energy', data: [], borderColor: '#00e5ff', backgroundColor: 'rgba(0,229,255,0.06)', fill: true },
        ],
    },
    options: { ...chartOpts },
});

// ── WebSocket ────────────────────────────────────────────────

function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        connectionBadge.classList.add('connected');
        connectionBadge.querySelector('.status-text').textContent = 'Connected';
    };

    ws.onclose = () => {
        connectionBadge.classList.remove('connected');
        connectionBadge.querySelector('.status-text').textContent = 'Disconnected';
        setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => { ws.close(); };

    ws.onmessage = (event) => {
        try {
            const state = JSON.parse(event.data);
            if (state.type === 'pong') return;
            lastState = state;
            updateDashboard(state);
        } catch (e) {
            console.warn('Parse error:', e);
        }
    };
}

// ── Dashboard Update ─────────────────────────────────────────

function updateDashboard(state) {
    // Tick
    tickDisplay.textContent = state.tick.toLocaleString();

    worldWidth = state.width;
    worldHeight = state.height;

    // Season & Time
    updateEnvironment(state);

    // Events (toast notifications)
    handleEvents(state.events || []);

    // Stats
    const stats = state.stats;
    if (stats && stats.population) {
        const pop = stats.population;
        animateCount(el.floraCount, pop.flora);
        animateCount(el.herbCount, pop.herbivores);
        animateCount(el.predCount, pop.predators);
        animateCount(el.omniCount, pop.omnivores);

        // Vitals ring
        const bioVal = stats.biodiversity || 0;
        el.biodiversity.textContent = bioVal.toFixed(2);
        setRingProgress(el.bioArc, bioVal); // 0-1 range already

        const engVal = stats.averages.energy || 0;
        el.avgEnergy.textContent = Math.round(engVal);
        setRingProgress(el.energyArc, engVal / 100);

        animateCount(el.totalBirths, stats.totals.births);
        animateCount(el.totalDeaths, stats.totals.deaths);

        // Trait bars
        const spd = stats.averages.speed || 0;
        const vis = stats.averages.vision || 0;
        const sz = stats.averages.size || 0;
        el.traitSpeed.style.width = `${Math.min(100, (spd / 3) * 100)}%`;
        el.traitVision.style.width = `${Math.min(100, (vis / 12) * 100)}%`;
        el.traitSize.style.width = `${Math.min(100, (sz / 3) * 100)}%`;
        el.traitSpeedVal.textContent = spd.toFixed(2);
        el.traitVisionVal.textContent = vis.toFixed(1);
        el.traitSizeVal.textContent = sz.toFixed(2);

        // Population trend
        if (stats.history && stats.history.herbivores.length > 2) {
            const h = stats.history.herbivores;
            const diff = h[h.length - 1] - h[h.length - 2];
            el.popTrend.textContent = diff > 0 ? `▲ +${diff}` : diff < 0 ? `▼ ${diff}` : '—';
            el.popTrend.style.color = diff > 0 ? '#39d98a' : diff < 0 ? '#ff6b6b' : '#505a6a';
        }

        updateCharts(stats);
    }

    renderWorld(state.entities, state.time_of_day);
}

// ── Environment ──────────────────────────────────────────────

function updateEnvironment(state) {
    const sc = SEASON_CONFIG[state.season] || SEASON_CONFIG.Spring;
    el.seasonIcon.textContent = sc.icon;
    el.seasonText.textContent = state.season;
    document.documentElement.style.setProperty('--season-tint', sc.tint);
    document.documentElement.style.setProperty('--season-hue', sc.hue);

    const tc = TIME_CONFIG[state.time_of_day] || TIME_CONFIG.DAY;
    el.timeIcon.textContent = tc.icon;
    el.timeText.textContent = state.time_of_day.charAt(0) + state.time_of_day.slice(1).toLowerCase();
}

function handleEvents(events) {
    // Detect new events
    for (const ev of events) {
        if (!previousEvents.includes(ev)) {
            showToast(ev);
        }
    }
    previousEvents = [...events];

    if (events.length > 0) {
        el.eventBadge.style.display = 'flex';
        el.eventText.textContent = events.join(', ');
    } else {
        el.eventBadge.style.display = 'none';
    }
}

function showToast(eventName) {
    const icons = { Rain: '🌧️', Drought: '🏜️', Storm: '⛈️' };
    const classes = { Rain: 'toast-rain', Drought: 'toast-drought', Storm: 'toast-storm' };

    const toast = document.createElement('div');
    toast.className = `toast ${classes[eventName] || ''}`;
    toast.innerHTML = `<span class="toast-icon">${icons[eventName] || '⚡'}</span>${eventName} event started`;
    toastContainer.appendChild(toast);

    setTimeout(() => toast.remove(), 4200);
}

// ── Smooth Counter Animation ─────────────────────────────────

function animateCount(element, newValue) {
    const current = parseInt(element.dataset.value || '0');
    if (current === newValue) return;

    element.dataset.value = newValue;
    const diff = newValue - current;
    const steps = Math.min(20, Math.abs(diff));
    const stepVal = diff / steps;
    let step = 0;

    function tick() {
        step++;
        const v = step >= steps ? newValue : Math.round(current + stepVal * step);
        element.textContent = v.toLocaleString();
        if (step < steps) requestAnimationFrame(tick);
        else element.style.animation = 'count-flash 0.5s ease';
    }

    element.style.animation = 'none';
    requestAnimationFrame(tick);
}

// ── SVG Ring Progress ────────────────────────────────────────

function setRingProgress(circle, pct) {
    const circumference = 2 * Math.PI * 15.9; // matches r="15.9"
    const offset = circumference - (Math.min(1, Math.max(0, pct)) * circumference);
    circle.style.strokeDasharray = circumference;
    circle.style.strokeDashoffset = offset;
}

// ── Chart Updates ────────────────────────────────────────────

function updateCharts(stats) {
    if (!stats.history) return;
    const labels = stats.history.herbivores.map((_, i) => i);

    populationChart.data.labels = labels;
    populationChart.data.datasets[0].data = stats.history.herbivores;
    populationChart.data.datasets[1].data = stats.history.predators;
    populationChart.data.datasets[2].data = stats.history.omnivores;
    populationChart.update('none');

    energyChart.data.labels = labels;
    energyChart.data.datasets[0].data = stats.history.energy;
    energyChart.update('none');
}

// ── World Rendering ──────────────────────────────────────────

function renderWorld(entities, timeOfDay) {
    const container = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = container.clientHeight;

    // Fix DPR scaling bug — fully reset before each frame
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    cellSize = Math.min(w / worldWidth, h / worldHeight);
    const offsetX = (w - cellSize * worldWidth) / 2;
    const offsetY = (h - cellSize * worldHeight) / 2;

    // Clear
    ctx.fillStyle = COLORS.BACKGROUND;
    ctx.fillRect(0, 0, w, h);

    // Subtle grid
    if (cellSize >= 6) {
        ctx.strokeStyle = COLORS.GRID_LINE;
        ctx.lineWidth = 0.5;
        for (let x = 0; x <= worldWidth; x++) {
            ctx.beginPath();
            ctx.moveTo(offsetX + x * cellSize, offsetY);
            ctx.lineTo(offsetX + x * cellSize, offsetY + worldHeight * cellSize);
            ctx.stroke();
        }
        for (let y = 0; y <= worldHeight; y++) {
            ctx.beginPath();
            ctx.moveTo(offsetX, offsetY + y * cellSize);
            ctx.lineTo(offsetX + worldWidth * cellSize, offsetY + y * cellSize);
            ctx.stroke();
        }
    }

    if (!entities) return;

    const flora = entities.filter(e => e.type === 'FLORA');
    const fauna = entities.filter(e => e.type !== 'FLORA');

    // Draw flora
    for (const e of flora) {
        const color = getFloraColor(e);
        const px = offsetX + e.x * cellSize;
        const py = offsetY + e.y * cellSize;
        const size = cellSize * getFloraScale(e);

        ctx.fillStyle = color;
        ctx.fillRect(
            px + (cellSize - size) / 2,
            py + (cellSize - size) / 2,
            size, size
        );
    }

    // Draw fauna with glow
    for (const e of fauna) {
        const color = COLORS[e.type] || '#ffffff';
        const px = offsetX + e.x * cellSize + cellSize / 2;
        const py = offsetY + e.y * cellSize + cellSize / 2;
        const radius = cellSize * 0.35 * Math.min(2, (e.size || 1));

        // Glow
        const gradient = ctx.createRadialGradient(px, py, 0, px, py, radius + 4);
        gradient.addColorStop(0, hexToRgba(color, 0.25));
        gradient.addColorStop(1, hexToRgba(color, 0));
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(px, py, radius + 4, 0, Math.PI * 2);
        ctx.fill();

        // Body
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(px, py, radius, 0, Math.PI * 2);
        ctx.fill();

        // Energy bar
        if (cellSize >= 6) {
            const barW = cellSize * 0.65;
            const barH = Math.max(1.5, cellSize * 0.08);
            const barX = px - barW / 2;
            const barY = py - radius - 3 - barH;
            const pct = Math.max(0, Math.min(1, (e.energy || 0) / 100));

            ctx.fillStyle = 'rgba(0,0,0,0.35)';
            roundRect(ctx, barX, barY, barW, barH, 1);
            ctx.fill();

            ctx.fillStyle = pct > 0.5 ? '#39d98a' : pct > 0.25 ? '#ffc145' : '#ff6b6b';
            roundRect(ctx, barX, barY, barW * pct, barH, 1);
            ctx.fill();
        }
    }

    // Night dimming overlay
    const dimLevel = TIME_CONFIG[timeOfDay]?.dim || 0;
    if (dimLevel > 0) {
        ctx.fillStyle = `rgba(4, 6, 12, ${dimLevel})`;
        ctx.fillRect(offsetX, offsetY, cellSize * worldWidth, cellSize * worldHeight);
    }
}

// ── Helpers ──────────────────────────────────────────────────

function getFloraColor(e) {
    const key = `${e.flora_type || 'GRASS'}_${e.stage || 'MATURE'}`;
    return COLORS[key] || COLORS.GRASS_MATURE;
}

function getFloraScale(e) {
    switch (e.stage || 'MATURE') {
        case 'SEED': return 0.25;
        case 'SPROUT': return 0.45;
        case 'MATURE': return 0.8;
        case 'DECAYING': return 0.5;
        default: return 0.6;
    }
}

function hexToRgba(hex, alpha) {
    if (hex.startsWith('rgba') || hex.startsWith('rgb')) {
        return hex.replace(/[\d.]+\)$/, alpha + ')');
    }
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.lineTo(x + w, y + h);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.lineTo(x, y + h);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
}

// ── Entity Inspector (click canvas) ──────────────────────────

canvas.addEventListener('click', (evt) => {
    if (!lastState || !lastState.entities) return;

    const rect = canvas.getBoundingClientRect();
    const mx = evt.clientX - rect.left;
    const my = evt.clientY - rect.top;

    const container = canvas.parentElement;
    const cw = container.clientWidth;
    const ch = container.clientHeight;
    cellSize = Math.min(cw / worldWidth, ch / worldHeight);
    const offsetX = (cw - cellSize * worldWidth) / 2;
    const offsetY = (ch - cellSize * worldHeight) / 2;

    const gx = Math.floor((mx - offsetX) / cellSize);
    const gy = Math.floor((my - offsetY) / cellSize);

    // Find nearest fauna within 2 cells
    const fauna = lastState.entities.filter(e => e.type !== 'FLORA');
    let best = null, bestDist = 3;
    for (const f of fauna) {
        const d = Math.hypot(f.x - gx, f.y - gy);
        if (d < bestDist) { bestDist = d; best = f; }
    }

    if (best) {
        showInspector(best, evt.clientX - rect.left, evt.clientY - rect.top);
    } else {
        el.entityInspector.style.display = 'none';
    }
});

function showInspector(entity, px, py) {
    const icons = { HERBIVORE: '🐇', PREDATOR: '🐺', OMNIVORE: '🦊' };
    const type = entity.species || entity.type;
    el.inspectorIcon.textContent = icons[type] || '❓';
    el.inspectorTitle.textContent = `${type.charAt(0) + type.slice(1).toLowerCase()} #${entity.id}`;

    const rows = [
        ['Energy', `${entity.energy}`],
        ['Hunger', `${entity.hunger || '—'}`],
        ['Age', `${entity.age} ticks`],
        ['Action', entity.action || '—'],
        ['Speed', entity.speed?.toFixed(2) || '—'],
        ['Vision', entity.vision?.toFixed(1) || '—'],
        ['Gen', `${entity.generation || 0}`],
    ];

    el.inspectorBody.innerHTML = rows.map(([k, v]) =>
        `<div class="inspect-row"><span>${k}</span><span class="inspect-val">${v}</span></div>`
    ).join('');

    const inspector = el.entityInspector;
    inspector.style.display = 'block';
    inspector.style.left = Math.min(px + 10, canvas.parentElement.clientWidth - 220) + 'px';
    inspector.style.top = Math.min(py + 10, canvas.parentElement.clientHeight - 200) + 'px';
}

el.inspectorClose.addEventListener('click', () => {
    el.entityInspector.style.display = 'none';
});

// ── Activity Feed ────────────────────────────────────────────

const activityFeed = document.getElementById('activityFeed');
const activityCountEl = document.getElementById('activityCount');
let activityCount = 0;
let prevPop = { herbivores: 0, predators: 0, omnivores: 0, flora: 0 };
let feedInitialized = false;
const MAX_FEED_ITEMS = 15;

function addActivity(icon, msg) {
    if (!feedInitialized) {
        activityFeed.innerHTML = '';
        feedInitialized = true;
    }

    const item = document.createElement('div');
    item.className = 'activity-item';
    const tick = lastState ? lastState.tick : 0;
    item.innerHTML = `<span class="activity-icon">${icon}</span><span class="activity-msg">${msg}</span><span class="activity-time">T${tick}</span>`;
    activityFeed.prepend(item);

    activityCount++;
    activityCountEl.textContent = `${activityCount} events`;

    // Remove old items
    while (activityFeed.children.length > MAX_FEED_ITEMS) {
        activityFeed.lastChild.remove();
    }
}

function trackActivity(state) {
    const stats = state.stats;
    if (!stats || !stats.population) return;

    const pop = stats.population;

    // Track births & deaths
    if (prevPop.herbivores > 0 || prevPop.predators > 0) {
        const herbDiff = pop.herbivores - prevPop.herbivores;
        const predDiff = pop.predators - prevPop.predators;
        const omniDiff = pop.omnivores - prevPop.omnivores;

        if (herbDiff > 0) addActivity('🐇', `${herbDiff} herbivore${herbDiff > 1 ? 's' : ''} born`);
        if (predDiff > 0) addActivity('🐺', `${predDiff} predator${predDiff > 1 ? 's' : ''} born`);
        if (omniDiff > 0) addActivity('🦊', `${omniDiff} omnivore${omniDiff > 1 ? 's' : ''} born`);

        if (herbDiff < 0) addActivity('💀', `${Math.abs(herbDiff)} herbivore${Math.abs(herbDiff) > 1 ? 's' : ''} died`);
        if (predDiff < 0) addActivity('💀', `${Math.abs(predDiff)} predator${Math.abs(predDiff) > 1 ? 's' : ''} died`);
        if (omniDiff < 0) addActivity('💀', `${Math.abs(omniDiff)} omnivore${Math.abs(omniDiff) > 1 ? 's' : ''} died`);

        // Milestones
        if (pop.flora > 3000 && prevPop.flora <= 3000) addActivity('🌿', 'Flora exceeded 3,000!');
        if (pop.herbivores + pop.predators + pop.omnivores === 0 && prevPop.herbivores + prevPop.predators + prevPop.omnivores > 0) {
            addActivity('☠️', 'All fauna have gone extinct!');
        }
    }

    prevPop = { ...pop };
}

// Hook into dashboard update
const _origUpdate = updateDashboard;
updateDashboard = function (state) {
    _origUpdate(state);
    trackActivity(state);
};

// ── Controls ─────────────────────────────────────────────────

document.getElementById('zoomSlider').addEventListener('input', (e) => {
    cellSize = parseInt(e.target.value);
    if (lastState) renderWorld(lastState.entities, lastState.time_of_day);
});

window.addEventListener('resize', () => {
    if (lastState) renderWorld(lastState.entities, lastState.time_of_day);
});

// ── Start ────────────────────────────────────────────────────

connect();
