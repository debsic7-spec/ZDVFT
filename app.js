/* ===== PEA TRACKER AI - APP.JS ===== */

const savedBackendUrl = localStorage.getItem('pea_backend_url') || '';
const API_URL = savedBackendUrl
    ? (savedBackendUrl.startsWith('http') ? `${savedBackendUrl}/api` : `http://${savedBackendUrl}:8000/api`)
    : `${window.location.origin}/api`;
const STATE = {
    currentIsin: 'FR0013341781',
    favorites: JSON.parse(localStorage.getItem('pea_favorites')) || ['FR0013341781'],
    alerts: JSON.parse(localStorage.getItem('pea_alerts')) || [],
    portfolio: JSON.parse(localStorage.getItem('pea_portfolio')) || {},
    allAssets: [],
    priceChart: null,
    volumeChart: null,
    currentTimeframe: (localStorage.getItem('pea_default_tf') && localStorage.getItem('pea_default_tf') !== 'null' && localStorage.getItem('pea_default_tf') !== 'undefined') ? localStorage.getItem('pea_default_tf') : '1d',
    chartType: 'line',
    currentData: null,
    apiOnline: false,
    refreshInterval: null,
    countdownInterval: null,
    lastPrice: null,
    marketOpen: true,
    searchTimeout: null,
    lastAiSignals: {}
};

/* =================== APK / MOBILE WRAPPER INIT =================== */
// Préparation pour Cordova / Capacitor ou PhoneGap.
// L'événement 'deviceready' est déclenché par le Webview natif quand l'app est prête.
document.addEventListener('deviceready', () => {
    console.log("APK Device Ready - Native functionalities enabled.");
    // Gérer le bouton retour matériel sur Android (Backbutton)
    document.addEventListener('backbutton', (e) => {
        const currentTab = document.querySelector('.tab.active').id;
        if (currentTab !== 'tab-home') {
            e.preventDefault();
            switchTab('home'); // Ramène au dashboard au lieu de fermer l'app
        } else {
            // Laisse l'app se fermer
        }
    }, false);
    
    // Reprise de l'application (Sortie de veille de l'OS) -> Force l'actualisation
    document.addEventListener('resume', () => {
        if (STATE.marketOpen) silentPriceRefresh();
    }, false);
}, false);

/* =================== INIT =================== */
document.addEventListener('DOMContentLoaded', async () => {
    setupNavigation();
    initCharts();
    setupControls();
    setupPortfolio();
    // Set active TF button from saved preference
    const savedTf = STATE.currentTimeframe;
    document.querySelectorAll('.tf-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-tf') === savedTf));
    await bootApp();
    startAutoRefresh();
    checkMarketStatus();

    // Ajout listeners pour Prédiction 1h et Tout actualiser à chaque affichage du dashboard
    function setupPredictionAndRefreshListeners() {
        const predictBtn = document.getElementById('trend-committee-btn');
        if (predictBtn && !predictBtn._hasListener) {
            predictBtn.addEventListener('click', async () => {
                await showFutureForecast();
            });
            predictBtn._hasListener = true;
        }
        const closeForecastBtn = document.getElementById('close-committee-panel');
        if (closeForecastBtn && !closeForecastBtn._hasListener) {
            closeForecastBtn.addEventListener('click', () => {
                document.getElementById('trend-committee-panel').style.display = 'none';
            });
            closeForecastBtn._hasListener = true;
        }
        const refreshCommitteeBtn = document.getElementById('refresh-committee-btn');
        if (refreshCommitteeBtn && !refreshCommitteeBtn._hasListener) {
            refreshCommitteeBtn.addEventListener('click', async () => {
                refreshCommitteeBtn.classList.add('spinning');
                await showFutureForecast();
                setTimeout(() => refreshCommitteeBtn.classList.remove('spinning'), 500);
            });
            refreshCommitteeBtn._hasListener = true;
        }
        const refreshAllBtn = document.getElementById('refresh-all-btn');
        if (refreshAllBtn && !refreshAllBtn._hasListener) {
            refreshAllBtn.addEventListener('click', async () => {
                refreshAllBtn.classList.add('spinning');
                await bootApp();
                await loadAssetDetail(STATE.currentIsin);
                await fetchOpportunities();
                renderScreener(STATE.allAssets);
                setTimeout(() => refreshAllBtn.classList.remove('spinning'), 1000);
            });
            refreshAllBtn._hasListener = true;
        }
    }
    setupPredictionAndRefreshListeners();
    // Réapplique les listeners à chaque changement de tab
    const allNavBtns = document.querySelectorAll('.nav-item, .m-nav');
    allNavBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            setTimeout(setupPredictionAndRefreshListeners, 100); // Laisse le DOM se mettre à jour
        });
    });
    // Force clear old service workers and caches on load
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations().then(regs => {
            regs.forEach(r => r.unregister());
        });
        caches.keys().then(keys => {
            keys.forEach(k => caches.delete(k));
        });
    }
// =================== PRÉDICTION FUTURE 1H ===================
async function showFutureForecast() {
    const panel = document.getElementById('trend-committee-panel');
    const ctx = document.getElementById('committeeChart').getContext('2d');
    if (!panel || !ctx) return;
    
    const wasHidden = panel.style.display === 'none';
    panel.style.display = 'block';
    if (wasHidden) {
        setTimeout(() => panel.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
    }

    const data = STATE.currentData;
    if (!data || !data.dataseries || data.dataseries.length < 10) return;

    const prices = data.dataseries;
    const lastPrice = prices[prices.length - 1];

    // Mathématiques Quantitatives : Mouvement Brownien Géométrique (GBM)
    // Calcul des rendements logarithmiques récents
    const lookback = Math.min(20, prices.length - 1);
    const logReturns = [];
    for (let i = 1; i <= lookback; i++) {
        const pCurrent = prices[prices.length - i];
        const pPrev = prices[prices.length - i - 1];
        if (pPrev > 0) logReturns.push(Math.log(pCurrent / pPrev));
    }
    
    // Dérive (Drift - Tendance moyenne) et Volatilité (Écart-type)
    const meanReturn = logReturns.reduce((a, b) => a + b, 0) / (logReturns.length || 1);
    const variance = logReturns.reduce((a, b) => a + Math.pow(b - meanReturn, 2), 0) / (logReturns.length || 1);
    const sigma = Math.sqrt(variance) || 0.001; // Volatilité

    // Ajustement par Retour à la moyenne (RSI)
    let drift = meanReturn;
    const rsi = data.rsi || 50;
    if (rsi > 70) drift -= (sigma * 0.6); // Pression baissière si suracheté
    else if (rsi < 30) drift += (sigma * 0.6); // Pression haussière si survendu

    const forecast = [];
    const labels = [];
    let price = lastPrice;
    for (let i = 1; i <= 12; i++) { // 12 x 5min = 1h
        // Transformation de Box-Muller pour obtenir un nombre aléatoire à distribution normale standard (Z)
        let u1 = Math.random(), u2 = Math.random();
        if (u1 === 0) u1 = 0.0001; // Éviter log(0)
        let z = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
        
        // Équation GBM : S_t = S_{t-1} * exp((mu - sigma^2 / 2) + sigma * Z)
        let shock = drift - (0.5 * Math.pow(sigma, 2)) + (sigma * z);
        price = price * Math.exp(shock);
        forecast.push(parseFloat(price.toFixed(2)));
        labels.push(`+${i * 5}m`);
    }
    // Affiche le graphique
    if (window.futureChartObj) window.futureChartObj.destroy();
    window.futureChartObj = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Prédiction (€)',
                data: forecast,
                borderColor: '#0891b2',
                backgroundColor: 'rgba(8,145,178,0.12)',
                fill: true,
                tension: 0.4,
                pointRadius: 2
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: true, grid: { color: 'rgba(8,145,178,0.08)' }, ticks: { color: '#0891b2', font: { size: 10 } } },
                y: { display: true, grid: { color: 'rgba(8,145,178,0.08)' }, ticks: { color: '#0891b2', font: { size: 10 } } }
            }
        }
    });
    // Texte d'interprétation
    const delta = forecast[forecast.length - 1] - lastPrice;
    const pct = (delta / lastPrice) * 100;
    let trendText = delta > 0 ? 'Hausse estimée' : 'Baisse estimée';
    if (Math.abs(pct) < 0.1) trendText = 'Stagnation probable';

    const txt = `${trendText} à ${(forecast[forecast.length - 1]).toFixed(2)} € (${delta > 0 ? '+' : ''}${pct.toFixed(2)}%) d'ici 1h.`;
    document.getElementById('committee-forecast-text').textContent = txt;
}
});

/* =================== TOAST NOTIFICATIONS =================== */
function showToast(message, type = 'error', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    const colors = { error: '#ef4444', success: '#22c55e', warn: '#f59e0b', info: '#6366f1' };
    toast.style.cssText = `pointer-events:auto;padding:12px 20px;border-radius:10px;color:#fff;font:600 13px/1.4 'Inter',sans-serif;background:${colors[type] || colors.info};box-shadow:0 4px 20px rgba(0,0,0,0.4);opacity:0;transform:translateX(30px);transition:all 0.3s ease;max-width:340px;`;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = '1'; toast.style.transform = 'translateX(0)'; });
    setTimeout(() => {
        toast.style.opacity = '0'; toast.style.transform = 'translateX(30px)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* =================== MARKET STATUS =================== */
async function checkMarketStatus() {
    try {
        const res = await fetch(`${API_URL}/market-status`);
        if (res.ok) {
            const s = await res.json();
            STATE.marketOpen = s.open;
            const badge = document.getElementById('market-badge');
            if (badge) {
                badge.textContent = s.open ? `Marché ouvert · ${s.time_cet}` : `Marché fermé · ${s.time_cet}`;
                badge.className = `market-badge ${s.open ? 'open' : 'closed'}`;
            }
        }
    } catch(e) {}
    // Re-check every 5 minutes
    setTimeout(checkMarketStatus, 5 * 60 * 1000);
}

/* =================== NAVIGATION =================== */
function setupNavigation() {
    // Sidebar + Mobile Nav sync
    const allNavBtns = document.querySelectorAll('.nav-item, .m-nav');
    allNavBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.getAttribute('data-tab');
            switchTab(tab);
        });
    });
}

function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-item, .m-nav').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-tab') === tabId);
    });
    document.getElementById(`tab-${tabId}`).classList.add('active');

    if (tabId === 'search') renderScreener(STATE.allAssets);
    if (tabId === 'favorites') renderFavorites();
    if (tabId === 'alerts') { renderAlerts(); populateAlertSelect(); renderAutoAlertLog(); loadAutoAlertToggle(); }
    if (tabId === 'opportunities') fetchOpportunities();
    if (tabId === 'settings') loadSettings();
}

/* =================== BOOT =================== */
async function bootApp() {
    try {
        const res = await fetch(`${API_URL}/scan`, { signal: AbortSignal.timeout(5000) });
        if (!res.ok) throw new Error('API Error');
        STATE.allAssets = await res.json();
        STATE.apiOnline = true;
        setApiStatus(true);
    } catch (e) {
        console.warn('API Backend Offline. Mode démo activé.', e);
        STATE.allAssets = getMockAssets();
        STATE.apiOnline = false;
        setApiStatus(false);
    }

    // Initial load
    await loadAssetDetail(STATE.currentIsin);

    // Load opportunities in background
    fetchOpportunities();

    // Auto-refresh opportunities every 5 minutes
    setInterval(fetchOpportunities, 5 * 60 * 1000);
}

/* =================== AUTO-REFRESH =================== */
function startAutoRefresh() {
    const INTERVAL = parseInt(localStorage.getItem('pea_refresh_interval')) || 30;
    let remaining = INTERVAL;
    const countEl = document.getElementById('countdown-sec');

    STATE.countdownInterval = setInterval(() => {
        remaining--;
        if (countEl) countEl.textContent = remaining;
        if (remaining <= 0) {
            remaining = INTERVAL;
            if (STATE.marketOpen) silentPriceRefresh();
        }
    }, 1000);
}

async function silentPriceRefresh() {
    if (!STATE.apiOnline) return;
    try {
        const res = await fetch(`${API_URL}/asset/${STATE.currentIsin}?period=${STATE.currentTimeframe}`, { signal: AbortSignal.timeout(8000) });
        if (!res.ok) return;
        const data = await res.json();

        // Pulse animation if price changed
        const priceEl = document.getElementById('current-price');
        if (STATE.lastPrice !== null && data.price !== STATE.lastPrice) {
            priceEl.classList.remove('price-updated');
            void priceEl.offsetWidth; // reflow
            priceEl.classList.add('price-updated');
        }
        STATE.lastPrice = data.price;

        // Update header prices only (don't redraw chart)
        document.getElementById('current-price').textContent = `${data.price.toFixed(2)} €`;
        const changeBadge = document.getElementById('current-change');
        const sign = data.change >= 0 ? '+' : '';
        changeBadge.textContent = `${sign}${data.change.toFixed(2)}%`;
        changeBadge.className = `change-badge ${data.change >= 0 ? 'positive' : 'negative'}`;

        // Update portfolio P&L
        updatePortfolioDisplay(data.price);

        // Check alerts
        checkAlerts(data);
    } catch (e) { /* silent */ }

    // Also check other favorites for AI alerts (background)
    scanFavoritesForAiAlerts();
}

async function scanFavoritesForAiAlerts() {
    if (localStorage.getItem('pea_auto_alerts') === 'false') return;
    for (const isin of STATE.favorites) {
        if (isin === STATE.currentIsin) continue; // Already checked above
        try {
            const res = await fetch(`${API_URL}/asset/${isin}?period=1d`, { signal: AbortSignal.timeout(5000) });
            if (!res.ok) continue;
            const data = await res.json();
            checkAiAutoAlert(data);
        } catch (e) { /* silent */ }
    }
}

function setApiStatus(online) {
    const dot = document.getElementById('api-status-dot');
    dot.querySelector('.status-dot').className = `status-dot ${online ? 'online' : 'offline'}`;
    dot.querySelector('span').textContent = online ? 'API Live' : 'Mode Démo';
}

/* =================== ASSET DETAIL =================== */
async function loadAssetDetail(isin) {
    STATE.currentIsin = isin;

    let data;
    if (STATE.apiOnline) {
        try {
            const res = await fetch(`${API_URL}/asset/${isin}?period=${STATE.currentTimeframe}`);
            if (!res.ok) throw new Error(`API ${res.status}`);
            data = await res.json();
            if (!data.name || data.name === 'undefined') {
                const known = STATE.allAssets.find(a => a.isin === isin);
                if (known) data.name = known.name;
            }
        } catch (e) {
            console.warn('Asset API error:', e);
            showToast(`Erreur chargement données: ${e.message}`, 'error');
            data = getMockDetail(isin);
        }
    } else {
        data = getMockDetail(isin);
    }

    STATE.currentData = data;
    updateHeader(data);
    updateChart(data);
    // Re-apply current chart type after data update
    if (STATE.chartType !== 'line') switchChartType(STATE.chartType, data);
    updateAI(data);
    updateStats(data);
    checkAlerts(data);
}

function updateHeader(data) {
    document.getElementById('asset-name').textContent = data.name;
    document.getElementById('asset-isin').textContent = `${data.isin} · ${data.ticker || ''}`;

    const priceEl = document.getElementById('current-price');
    if (STATE.lastPrice !== null && data.price !== STATE.lastPrice) {
        priceEl.classList.remove('price-updated');
        void priceEl.offsetWidth;
        priceEl.classList.add('price-updated');
    }
    STATE.lastPrice = data.price;
    priceEl.textContent = `${data.price.toFixed(2)} €`;
    
    const changeBadge = document.getElementById('current-change');
    const sign = data.change >= 0 ? '+' : '';
    changeBadge.textContent = `${sign}${data.change.toFixed(2)}%`;
    changeBadge.className = `change-badge ${data.change >= 0 ? 'positive' : 'negative'}`;

    // Fav button
    const favBtn = document.getElementById('fav-toggle-btn');
    const isFav = STATE.favorites.includes(data.isin);
    favBtn.className = isFav ? 'fav-active' : '';
    favBtn.onclick = () => {
        toggleFavorite(data.isin);
        const nowFav = STATE.favorites.includes(data.isin);
        favBtn.className = nowFav ? 'fav-active' : '';
    };

    // Portfolio P&L
    updatePortfolioDisplay(data.price);

    // Notification btn
    document.getElementById('noti-btn').onclick = () => requestNotification(data);
}


/* =================== CHARTS =================== */
function initCharts() {
    const priceCtx = document.getElementById('priceChart').getContext('2d');
    const volCtx = document.getElementById('volumeChart').getContext('2d');

    const priceGrad = priceCtx.createLinearGradient(0, 0, 0, 260);
    priceGrad.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
    priceGrad.addColorStop(1, 'rgba(99, 102, 241, 0)');

    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";

    STATE.priceChart = new Chart(priceCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Prix (€)',
                    data: [],
                    borderColor: '#6366f1',
                    backgroundColor: priceGrad,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: '#6366f1',
                    fill: true,
                    tension: 0.3,
                    order: 1
                },
                {
                    label: 'VWAP',
                    data: [],
                    borderColor: '#0891b2',
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    pointRadius: 0,
                    fill: false,
                    tension: 0.4,
                    spanGaps: true,
                    order: 2
                },
                {   // Index 2: SMA 20
                    label: 'SMA 20',
                    data: [],
                    borderColor: '#f59e0b',
                    borderWidth: 1.2,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3,
                    hidden: true,
                    spanGaps: true,
                    order: 3
                },
                {   // Index 3: SMA 50
                    label: 'SMA 50',
                    data: [],
                    borderColor: '#a855f7',
                    borderWidth: 1.2,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3,
                    hidden: true,
                    spanGaps: true,
                    order: 4
                },
                {   // Index 4: Bollinger Upper
                    label: 'BB Haut',
                    data: [],
                    borderColor: 'rgba(148,163,184,0.5)',
                    borderWidth: 1,
                    borderDash: [2, 2],
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3,
                    hidden: true,
                    spanGaps: true,
                    order: 5
                },
                {   // Index 5: Bollinger Lower (fill between)
                    label: 'BB Bas',
                    data: [],
                    borderColor: 'rgba(148,163,184,0.5)',
                    borderWidth: 1,
                    borderDash: [2, 2],
                    pointRadius: 0,
                    backgroundColor: 'rgba(148,163,184,0.08)',
                    fill: '-1',
                    tension: 0.3,
                    hidden: true,
                    spanGaps: true,
                    order: 6
                },
                {   // Index 6: Buy Signals (Backtest)
                    label: 'Achat (Backtest)',
                    data: [],
                    type: 'scatter',
                    backgroundColor: '#22c55e',
                    pointRadius: 6, pointHoverRadius: 8,
                    pointStyle: 'triangle',
                    hidden: true,
                    order: 0
                },
                {   // Index 7: Sell Signals (Backtest)
                    label: 'Vente (Backtest)',
                    data: [],
                    type: 'scatter',
                    backgroundColor: '#ef4444',
                    pointRadius: 6, pointHoverRadius: 8,
                    pointStyle: 'triangle', rotation: 180, // Triangle inversé
                    hidden: true,
                    order: 0
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 500 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index', intersect: false,
                    backgroundColor: 'rgba(13, 20, 32, 0.95)',
                    borderColor: 'rgba(99,102,241,0.3)',
                    borderWidth: 1,
                    titleColor: '#94a3b8',
                    bodyColor: '#f1f5f9',
                    titleFont: { family: "'JetBrains Mono', monospace", size: 11 },
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                    callbacks: {
                        label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2)} €`
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: { color: 'rgba(71,85,105,0.15)', drawBorder: false },
                    ticks: { font: { size: 10, family: "'Inter', sans-serif" }, maxTicksLimit: 8, color: '#475569' }
                },
                y: {
                    display: true,
                    position: 'right',
                    beginAtZero: false,
                    grid: { color: 'rgba(71,85,105,0.15)', drawBorder: false },
                    ticks: { font: { size: 10, family: "'JetBrains Mono', monospace" }, color: '#475569', callback: (v) => v.toFixed(2) }
                }
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: false }
        }
    });

    STATE.volumeChart = new Chart(volCtx, {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Volume', data: [], backgroundColor: [], borderRadius: 2 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 500 },
            plugins: { legend: { display: false }, tooltip: {
                backgroundColor: 'rgba(13,20,32,0.95)',
                borderColor: 'rgba(99,102,241,0.3)', borderWidth: 1,
                callbacks: { label: (ctx) => ` Vol: ${formatVolume(ctx.parsed.y)}` }
            }},
            scales: {
                x: { display: false },
                y: { display: false }
            }
        }
    });
}

function updateChart(data) {
    const chart = STATE.priceChart;
    const isPositive = data.change >= 0;

    const ctx = document.getElementById('priceChart').getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 260);
    if (isPositive) {
        grad.addColorStop(0, 'rgba(34, 197, 94, 0.3)');
        grad.addColorStop(1, 'rgba(34, 197, 94, 0)');
        chart.data.datasets[0].borderColor = '#22c55e';
    } else {
        grad.addColorStop(0, 'rgba(239, 68, 68, 0.3)');
        grad.addColorStop(1, 'rgba(239, 68, 68, 0)');
        chart.data.datasets[0].borderColor = '#ef4444';
    }
    chart.data.datasets[0].backgroundColor = grad;

    chart.data.labels = data.labels;
    chart.data.datasets[0].data = data.dataseries;
    const cleanVwap = data.vwapSeries ? data.vwapSeries.map(v => (v && v > 0) ? v : null) : [];
    chart.data.datasets[1].data = cleanVwap;

    // Overlays: SMA20, SMA50, BB
    const cleanArr = (arr) => arr ? arr.map(v => (v && v > 0) ? v : null) : [];
    chart.data.datasets[2].data = cleanArr(data.sma20);
    chart.data.datasets[3].data = cleanArr(data.sma50);
    chart.data.datasets[4].data = cleanArr(data.bbUpper);
    chart.data.datasets[5].data = cleanArr(data.bbLower);

    // Signaux Backtest
    const showSignals = document.getElementById('show-signals')?.checked;
    chart.data.datasets[6].data = data.buySignals || [];
    chart.data.datasets[7].data = data.sellSignals || [];
    chart.data.datasets[6].hidden = !showSignals;
    chart.data.datasets[7].hidden = !showSignals;

    const showVwap = document.getElementById('show-vwap')?.checked;
    chart.data.datasets[1].hidden = !showVwap;

    // Auto-scale Y axis to visible data
    const visiblePrices = [...data.dataseries];
    if (showVwap) visiblePrices.push(...cleanVwap);
    if (!chart.data.datasets[2].hidden && data.sma20) visiblePrices.push(...data.sma20);
    if (!chart.data.datasets[4].hidden && data.bbUpper) visiblePrices.push(...data.bbUpper);
    if (!chart.data.datasets[5].hidden && data.bbLower) visiblePrices.push(...data.bbLower);
    if (showSignals && data.buySignals) visiblePrices.push(...cleanArr(data.buySignals));
    if (showSignals && data.sellSignals) visiblePrices.push(...cleanArr(data.sellSignals));

    const filtered = visiblePrices.filter(v => v != null && isFinite(v) && v > 0);
    if (filtered.length > 0) {
        const minP = Math.min(...filtered), maxP = Math.max(...filtered);
        const range = maxP - minP || maxP * 0.02, pad = range * 0.15;
        chart.options.scales.y.min = Math.floor((minP - pad) * 100) / 100;
        chart.options.scales.y.max = Math.ceil((maxP + pad) * 100) / 100;
    }
    chart.update();

    // Update volume
    if (data.volumeSeries) {
        const volColors = data.volumeSeries.map((_, i) => {
            if (i === 0) return 'rgba(99,102,241,0.5)';
            return data.dataseries[i] >= data.dataseries[i-1] ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)';
        });
        STATE.volumeChart.data.labels = data.labels;
        STATE.volumeChart.data.datasets[0].data = data.volumeSeries;
        STATE.volumeChart.data.datasets[0].backgroundColor = volColors;
        STATE.volumeChart.update();
    }

    // Stats row
    const pr = data.dataseries;
    document.getElementById('stat-open').textContent = (data.dayOpen ?? pr[0])?.toFixed(2) + ' €' || '--';
    document.getElementById('stat-high').textContent = (data.dayHigh ?? Math.max(...(data.highSeries || pr))).toFixed(2) + ' €';
    document.getElementById('stat-low').textContent = (data.dayLow ?? Math.min(...(data.lowSeries || pr))).toFixed(2) + ' €';
    const lastVwap = data.vwapSeries?.[data.vwapSeries.length - 1];
    document.getElementById('stat-vwap').textContent = lastVwap ? lastVwap.toFixed(2) + ' €' : '--';
    document.getElementById('stat-vol').textContent = data.volumeSeries ? formatVolume(data.volumeSeries.reduce((a,b) => a+b, 0)) : '--';
}

/* =================== CHART TYPE SWITCH =================== */
function rescaleYAxis() {
    const chart = STATE.priceChart;
    if (!chart || !STATE.currentData) return;
    const data = STATE.currentData;
    const visiblePrices = [...data.dataseries];
    const showVwap = document.getElementById('show-vwap')?.checked;
    const showSma = document.getElementById('show-sma')?.checked;
    const showBb = document.getElementById('show-bb')?.checked;
    const showSignals = document.getElementById('show-signals')?.checked;
    const cleanArr = (arr) => arr ? arr.filter(v => v != null && isFinite(v) && v > 0) : [];
    if (showVwap && data.vwapSeries) visiblePrices.push(...cleanArr(data.vwapSeries));
    if (showSma && data.sma20) visiblePrices.push(...cleanArr(data.sma20));
    if (showSma && data.sma50) visiblePrices.push(...cleanArr(data.sma50));
    if (showBb && data.bbUpper) visiblePrices.push(...cleanArr(data.bbUpper));
    if (showBb && data.bbLower) visiblePrices.push(...cleanArr(data.bbLower));
    if (showSignals && data.buySignals) visiblePrices.push(...cleanArr(data.buySignals));
    if (showSignals && data.sellSignals) visiblePrices.push(...cleanArr(data.sellSignals));
    const filtered = visiblePrices.filter(v => v != null && isFinite(v) && v > 0);
    if (filtered.length > 0) {
        const minP = Math.min(...filtered), maxP = Math.max(...filtered);
        const range = maxP - minP || maxP * 0.02, pad = range * 0.15;
        chart.options.scales.y.min = Math.floor((minP - pad) * 100) / 100;
        chart.options.scales.y.max = Math.ceil((maxP + pad) * 100) / 100;
    }
    chart.update();
}

function switchChartType(type, data) {
    STATE.chartType = type;
    if (!data) data = STATE.currentData;
    if (!data) return;

    const ctx = document.getElementById('priceChart').getContext('2d');
    const isPositive = data.change >= 0;

    if (type === 'candle') {
        // Rebuild chart as candlestick
        STATE.priceChart.destroy();
        const ohlcData = (data.openSeries && data.highSeries && data.lowSeries)
            ? data.dataseries.map((c, i) => ({ x: i, o: data.openSeries[i], h: data.highSeries[i], l: data.lowSeries[i], c }))
            : (data.ohlc && data.ohlc.length > 0)
            ? data.ohlc.map((d, i) => ({ x: i, o: d.o, h: d.h, l: d.l, c: d.c }))
            : data.dataseries.map((c, i) => {
                  // Simulate OHLC from close only (fallback)
                  const prev = i > 0 ? data.dataseries[i - 1] : c;
                  const noise = c * 0.003;
                  return { x: i, o: prev, h: Math.max(c, prev) + noise, l: Math.min(c, prev) - noise, c };
              });

        // Compute Y range from OHLC
        const allOhlcPrices = ohlcData.flatMap(d => [d.o, d.h, d.l, d.c]).filter(v => v != null && isFinite(v));
        let candleYMin, candleYMax;
        if (allOhlcPrices.length > 0) {
            const mn = Math.min(...allOhlcPrices), mx = Math.max(...allOhlcPrices);
            const rng = mx - mn || mx * 0.02, pad = rng * 0.15;
            candleYMin = Math.floor((mn - pad) * 100) / 100;
            candleYMax = Math.ceil((mx + pad) * 100) / 100;
        }

        STATE.priceChart = new Chart(ctx, {
            type: 'candlestick',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'OHLC',
                    data: ohlcData,
                    color: { up: '#22c55e', down: '#ef4444', unchanged: '#94a3b8' }
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 400 },
                plugins: { legend: { display: false }, tooltip: {
                    backgroundColor: 'rgba(13,20,32,0.95)',
                    borderColor: 'rgba(99,102,241,0.3)', borderWidth: 1,
                    bodyColor: '#f1f5f9',
                    callbacks: { label: (ctx) => ` O:${ctx.parsed.o?.toFixed(2)} H:${ctx.parsed.h?.toFixed(2)} L:${ctx.parsed.l?.toFixed(2)} C:${ctx.parsed.c?.toFixed(2)}` }
                }},
                scales: {
                    x: { type: 'category', ticks: { font: { size: 10 }, maxTicksLimit: 8, color: '#475569' }, grid: { color: 'rgba(71,85,105,0.15)' } },
                    y: { position: 'right', beginAtZero: false, min: candleYMin, max: candleYMax, ticks: { font: { size: 10, family: "'JetBrains Mono'" }, color: '#475569', callback: (v) => v.toFixed(2) }, grid: { color: 'rgba(71,85,105,0.15)' } }
                }
            }
        });
        return;
    }

    // Restore line chart if was candlestick
    if (STATE.priceChart.config.type === 'candlestick') {
        STATE.priceChart.destroy();
        const grad = ctx.createLinearGradient(0, 0, 0, 260);
        grad.addColorStop(0, 'rgba(99,102,241,0.3)');
        grad.addColorStop(1, 'rgba(99,102,241,0)');
        STATE.priceChart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [
                { label: 'Prix (€)', data: [], borderColor: '#6366f1', backgroundColor: grad, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, fill: true, tension: 0.3, order: 1 },
                { label: 'VWAP', data: [], borderColor: '#0891b2', borderWidth: 1.5, borderDash: [5,3], pointRadius: 0, fill: false, tension: 0.3, spanGaps: true, order: 2 },
                { label: 'SMA 20', data: [], borderColor: '#f59e0b', borderWidth: 1.2, pointRadius: 0, fill: false, tension: 0.3, hidden: true, spanGaps: true, order: 3 },
                { label: 'SMA 50', data: [], borderColor: '#a855f7', borderWidth: 1.2, pointRadius: 0, fill: false, tension: 0.3, hidden: true, spanGaps: true, order: 4 },
                { label: 'BB Haut', data: [], borderColor: 'rgba(148,163,184,0.5)', borderWidth: 1, borderDash: [2,2], pointRadius: 0, fill: false, tension: 0.3, hidden: true, spanGaps: true, order: 5 },
                { label: 'BB Bas', data: [], borderColor: 'rgba(148,163,184,0.5)', borderWidth: 1, borderDash: [2,2], pointRadius: 0, backgroundColor: 'rgba(148,163,184,0.08)', fill: '-1', tension: 0.3, hidden: true, spanGaps: true, order: 6 },
                { label: 'Achat', data: [], type: 'scatter', backgroundColor: '#22c55e', pointRadius: 6, pointHoverRadius: 8, pointStyle: 'triangle', hidden: true, order: 0 },
                { label: 'Vente', data: [], type: 'scatter', backgroundColor: '#ef4444', pointRadius: 6, pointHoverRadius: 8, pointStyle: 'triangle', rotation: 180, hidden: true, order: 0 }
            ]},
            options: STATE.priceChart?.options || {}
        });
    }

    const chart = STATE.priceChart;
    const grad = ctx.createLinearGradient(0, 0, 0, 260);

    if (type === 'area') {
        const fillColor = isPositive ? [0.4, '#22c55e'] : [0.4, '#ef4444'];
        grad.addColorStop(0, `rgba(${isPositive ? '34,197,94' : '239,68,68'}, 0.45)`);
        grad.addColorStop(0.6, `rgba(${isPositive ? '34,197,94' : '239,68,68'}, 0.1)`);
        grad.addColorStop(1, `rgba(${isPositive ? '34,197,94' : '239,68,68'}, 0)`);
        delete chart.data.datasets[0].type;
        chart.data.datasets[0].fill = true;
        chart.data.datasets[0].backgroundColor = grad;
        chart.data.datasets[0].borderColor = isPositive ? '#22c55e' : '#ef4444';
        chart.data.datasets[0].borderWidth = 2;
        chart.data.datasets[0].tension = 0.4;

    } else if (type === 'bar') {
        chart.data.datasets[0].type = 'bar';
        const barColors = data.dataseries.map((v, i) => {
            if (i === 0) return 'rgba(99,102,241,0.7)';
            return data.dataseries[i] >= data.dataseries[i-1] ? 'rgba(34,197,94,0.7)' : 'rgba(239,68,68,0.7)';
        });
        chart.data.datasets[0].backgroundColor = barColors;
        chart.data.datasets[0].borderColor = 'transparent';
        chart.data.datasets[0].fill = false;
        chart.data.datasets[0].tension = 0;

    } else { // line (default)
        delete chart.data.datasets[0].type;
        if (isPositive) {
            grad.addColorStop(0, 'rgba(34,197,94,0.3)');
            grad.addColorStop(1, 'rgba(34,197,94,0)');
            chart.data.datasets[0].borderColor = '#22c55e';
        } else {
            grad.addColorStop(0, 'rgba(239,68,68,0.3)');
            grad.addColorStop(1, 'rgba(239,68,68,0)');
            chart.data.datasets[0].borderColor = '#ef4444';
        }
        chart.data.datasets[0].backgroundColor = grad;
        chart.data.datasets[0].fill = true;
        chart.data.datasets[0].tension = 0.3;
    }

    chart.data.labels = data.labels;
    chart.data.datasets[0].data = data.dataseries;
    const cleanVwap2 = data.vwapSeries ? data.vwapSeries.map(v => (v && v > 0) ? v : null) : [];
    chart.data.datasets[1].data = cleanVwap2;
    const showVwap2 = document.getElementById('show-vwap')?.checked;
    chart.data.datasets[1].hidden = !showVwap2;

    // Set overlays
    const cleanArr2 = (arr) => arr ? arr.map(v => (v && v > 0) ? v : null) : [];
    if (chart.data.datasets[2]) chart.data.datasets[2].data = cleanArr2(data.sma20);
    if (chart.data.datasets[3]) chart.data.datasets[3].data = cleanArr2(data.sma50);
    if (chart.data.datasets[4]) chart.data.datasets[4].data = cleanArr2(data.bbUpper);
    if (chart.data.datasets[5]) chart.data.datasets[5].data = cleanArr2(data.bbLower);
    
    const showSignals = document.getElementById('show-signals')?.checked;
    if (chart.data.datasets[6]) { chart.data.datasets[6].data = cleanArr2(data.buySignals); chart.data.datasets[6].hidden = !showSignals; }
    if (chart.data.datasets[7]) { chart.data.datasets[7].data = cleanArr2(data.sellSignals); chart.data.datasets[7].hidden = !showSignals; }

    // Auto-scale Y axis
    const prices2 = [...data.dataseries, ...(showVwap2 ? cleanVwap2 : [])];
    if (showSignals && data.buySignals) prices2.push(...cleanArr2(data.buySignals));
    if (showSignals && data.sellSignals) prices2.push(...cleanArr2(data.sellSignals));
    
    const filtered2 = prices2.filter(v => v != null && isFinite(v) && v > 0);
    if (filtered2.length > 0) {
        const mn = Math.min(...filtered2), mx = Math.max(...filtered2);
        const rng = mx - mn || mx * 0.02, pad = rng * 0.15;
        chart.options.scales.y.min = Math.floor((mn - pad) * 100) / 100;
        chart.options.scales.y.max = Math.ceil((mx + pad) * 100) / 100;
    }

    chart.update();
}


function updateAI(data) {
    const verdictEl = document.getElementById('verdict-text');
    const detailEl = document.getElementById('verdict-detail');
    const confEl = document.getElementById('ai-confidence');

    verdictEl.textContent = data.ai_status || 'GARDER';
    detailEl.textContent = data.ai_details || 'Données insuffisantes.';

    if (data.ai_status?.includes('ACHETER')) { verdictEl.className = 'verdict-label buy'; }
    else if (data.ai_status?.includes('VENDRE')) { verdictEl.className = 'verdict-label sell'; }
    else { verdictEl.className = 'verdict-label wait'; }

    // RSI Bar
    const rsi = data.rsi || 50;
    const rsiColor = rsi > 70 ? '#ef4444' : rsi < 35 ? '#22c55e' : '#f59e0b';
    document.getElementById('rsi-bar').style.width = `${rsi}%`;
    document.getElementById('rsi-bar').style.background = rsiColor;
    document.getElementById('rsi-val').textContent = rsi.toFixed(1);

    // MACD Bar (normalize around 0)
    const macdRaw = data.macd || 0;
    const macdPct = Math.min(100, Math.max(0, (macdRaw + 5) * 10)); // Scale
    const macdColor = macdRaw > 0 ? '#22c55e' : '#ef4444';
    document.getElementById('macd-bar').style.width = `${macdPct}%`;
    document.getElementById('macd-bar').style.background = macdColor;
    document.getElementById('macd-val').textContent = macdRaw.toFixed(2);

    // VWAP signal
    const vwapPct = data.vwap_signal_pct ?? 50;
    const vwapColor = vwapPct > 50 ? '#22c55e' : '#ef4444';
    document.getElementById('vwap-bar').style.width = `${vwapPct}%`;
    document.getElementById('vwap-bar').style.background = vwapColor;
    document.getElementById('vwap-val').textContent = vwapPct > 50 ? 'Au-dessus' : 'En-dessous';

    // Confidence score (simple aggregate)
    let confidence = 50;
    if (data.rsi) {
        if (data.ai_status?.includes('ACHETER') && data.rsi < 35) confidence = 78;
        else if (data.ai_status?.includes('VENDRE') && data.rsi > 70) confidence = 82;
        else confidence = 55;
    }
    confEl.textContent = `${confidence}% confiance`;
}

function updateStats(data) {
    document.getElementById('s-price').textContent = `${data.price.toFixed(2)} €`;
    const sign = data.change >= 0 ? '+' : '';
    const s = document.getElementById('s-change');
    s.textContent = `${sign}${data.change.toFixed(2)}%`;
    s.className = `stat-big ${data.change >= 0 ? 'positive' : 'negative'}`;
    document.getElementById('s-high52').textContent = data.high52 ? `${data.high52.toFixed(2)} €` : '--';
    document.getElementById('s-low52').textContent = data.low52 ? `${data.low52.toFixed(2)} €` : '--';
}

/* =================== SCREENER =================== */
function renderScreener(assets) {
    const list = document.getElementById('screener-list');
    list.innerHTML = '';
    if (assets.length === 0) {
        list.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Chargement...</p></div>';
        return;
    }
    assets.forEach((asset, i) => {
        const item = buildScreenerItem(asset, i + 1);
        list.appendChild(item);
    });
}

function buildScreenerItem(asset, rank) {
    const div = document.createElement('div');
    div.className = 'screener-item';

    const isPos = asset.change >= 0;
    const sign = isPos ? '+' : '';
    const aiBadgeClass = asset.ai_status?.includes('ACHETER') ? 'buy' : asset.ai_status?.includes('VENDRE') ? 'sell' : 'wait';
    const aiBadgeText = asset.ai_status?.includes('ACHETER') ? '↑ Achat' : asset.ai_status?.includes('VENDRE') ? '↓ Vente' : '~ Neutre';

    div.innerHTML = `
        <div class="item-rank">${rank}</div>
        <div class="item-info">
            <span class="sym">${asset.name || asset.isin}</span>
            <span class="nm">${asset.isin}</span>
        </div>
        <div class="item-price">
            <span class="pv">${asset.price.toFixed(2)} €</span>
            <span class="ai-badge ${aiBadgeClass}">${aiBadgeText}</span>
        </div>
        <span class="item-change ${isPos ? 'positive' : 'negative'}">${sign}${asset.change.toFixed(2)}%</span>
    `;

    div.addEventListener('click', () => {
        loadAssetDetail(asset.isin);
        switchTab('home');
    });

    return div;
}

function renderFavorites() {
    const list = document.getElementById('favorites-list');
    list.innerHTML = '';
    const favs = STATE.allAssets.filter(a => STATE.favorites.includes(a.isin));
    if (favs.length === 0) {
        list.innerHTML = '<p class="empty-state">Aucun favori. Ajoutez des actifs depuis le Screener.</p>';
        return;
    }
    favs.forEach((asset, i) => list.appendChild(buildScreenerItem(asset, i + 1)));
}

function toggleFavorite(isin) {
    const idx = STATE.favorites.indexOf(isin);
    if (idx > -1) STATE.favorites.splice(idx, 1);
    else STATE.favorites.push(isin);
    localStorage.setItem('pea_favorites', JSON.stringify(STATE.favorites));
}

/* =================== OPPORTUNITIES =================== */
async function fetchOpportunities() {
    if (!STATE.apiOnline) {
        renderOpportunities(getMockOpportunities());
        return;
    }
    try {
        const res = await fetch(`${API_URL}/opportunities`, { signal: AbortSignal.timeout(30000) });
        if (!res.ok) throw new Error('API error');
        const data = await res.json();
        renderOpportunities(data);
        updateDashboardOppWidget(data);
        const now = new Date();
        const timeStr = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        const el = document.getElementById('opp-last-update');
        if (el) el.textContent = `Dernière analyse : ${timeStr}`;
    } catch (e) {
        console.warn('Opportunity fetch failed:', e);
        renderOpportunities(getMockOpportunities());
    }
}

function renderOpportunities(opportunities) {
    const list = document.getElementById('opp-list');
    if (!list) return;
    list.innerHTML = '';

    if (opportunities.length === 0) {
        list.innerHTML = '<p class="empty-state">Aucune opportunité détectée pour le moment. Le marché est neutre.</p>';
        return;
    }

    opportunities.forEach(opp => {
        const card = document.createElement('div');
        const isForte = opp.score >= 70;
        const isMedium = opp.score >= 45 && opp.score < 70;
        card.className = `opp-card ${isForte ? 'forte-card' : isMedium ? 'medium-card' : ''}`;

        const scoreColor = isForte ? 'var(--green)' : isMedium ? 'var(--accent)' : 'var(--amber)';
        const badgeClass = isForte ? 'forte' : isMedium ? 'medium' : 'watch';
        const sign = opp.change >= 0 ? '+' : '';
        const changeColor = opp.change >= 0 ? 'var(--green)' : 'var(--red)';

        card.innerHTML = `
            <div class="opp-card-header">
                <div>
                    <span class="opp-badge ${badgeClass} opp-card-badge">${opp.label}</span>
                    <span class="opp-name">${opp.name}</span>
                    <span class="opp-isin">${opp.isin}</span>
                </div>
                <div class="opp-score-ring">
                    <span class="score-num" style="color:${scoreColor}">${opp.score}</span>
                    <span class="score-label">/ 100</span>
                </div>
            </div>
            <div class="opp-stats">
                <div class="opp-stat">
                    <span class="opp-stat-label">Prix</span>
                    <strong>${opp.price.toFixed(2)} €</strong>
                </div>
                <div class="opp-stat">
                    <span class="opp-stat-label">Variation</span>
                    <strong style="color:${changeColor}">${sign}${opp.change.toFixed(2)}%</strong>
                </div>
                <div class="opp-stat">
                    <span class="opp-stat-label">RSI</span>
                    <strong style="color:${opp.rsi < 35 ? 'var(--green)' : opp.rsi > 70 ? 'var(--red)' : 'var(--text)'}">${opp.rsi}</strong>
                </div>
                <div class="opp-stat">
                    <span class="opp-stat-label">Volatilité ATR</span>
                    <strong style="color:var(--accent)">${opp.atr ?? '--'} %</strong>
                </div>
            </div>
            <div class="opp-reasons">
                ${(opp.reasons || []).map(r => `<div class="opp-reason">${r}</div>`).join('')}
            </div>
        `;

        card.addEventListener('click', () => {
            loadAssetDetail(opp.isin);
            switchTab('home');
        });

        list.appendChild(card);
    });
}

function updateDashboardOppWidget(opportunities) {
    // Remove existing widget if any
    const existing = document.getElementById('opp-dashboard-widget');
    if (existing) existing.remove();

    const top3 = opportunities.slice(0, 3);
    if (top3.length === 0) return;

    const widget = document.createElement('div');
    widget.id = 'opp-dashboard-widget';
    widget.className = 'opp-widget';
    widget.innerHTML = `
        <div class="opp-widget-header">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            Top Opportunités IA détectées
        </div>
        <div class="opp-widget-items">
            ${top3.map(o => `
                <div class="opp-widget-item" data-isin="${o.isin}">
                    <span><strong>${o.name}</strong> · RSI ${o.rsi}</span>
                    <span style="color:var(--green);font-weight:700;">Score ${o.score}/100</span>
                </div>
            `).join('')}
        </div>
    `;

    widget.querySelectorAll('.opp-widget-item').forEach(el => {
        el.addEventListener('click', () => {
            loadAssetDetail(el.getAttribute('data-isin'));
        });
    });

    // Insert before chart panel
    const chartPanel = document.querySelector('.chart-panel');
    if (chartPanel) chartPanel.parentNode.insertBefore(widget, chartPanel);
}

/* =================== PORTFOLIO =================== */
function setupPortfolio() {
    document.getElementById('pw-edit-btn')?.addEventListener('click', () => {
        const isin = STATE.currentIsin;
        const pos = STATE.portfolio[isin];
        document.getElementById('pf-shares').value = pos?.shares || '';
        document.getElementById('pf-avg').value = pos?.avgPrice || '';
        document.getElementById('portfolio-form').style.display = 'block';
        document.getElementById('portfolio-widget').style.display = 'none';
    });

    document.getElementById('pf-save')?.addEventListener('click', () => {
        const isin = STATE.currentIsin;
        const shares = parseFloat(document.getElementById('pf-shares').value);
        const avgPrice = parseFloat(document.getElementById('pf-avg').value);
        if (!isNaN(shares) && shares > 0 && !isNaN(avgPrice)) {
            STATE.portfolio[isin] = { shares, avgPrice };
            localStorage.setItem('pea_portfolio', JSON.stringify(STATE.portfolio));
        } else {
            delete STATE.portfolio[isin];
            localStorage.setItem('pea_portfolio', JSON.stringify(STATE.portfolio));
        }
        document.getElementById('portfolio-form').style.display = 'none';
        updatePortfolioDisplay(STATE.lastPrice);
    });

    document.getElementById('pf-cancel')?.addEventListener('click', () => {
        document.getElementById('portfolio-form').style.display = 'none';
        const pos = STATE.portfolio[STATE.currentIsin];
        document.getElementById('portfolio-widget').style.display = pos ? 'flex' : 'none';
    });
}

function updatePortfolioDisplay(currentPrice) {
    const isin = STATE.currentIsin;
    const pos = STATE.portfolio[isin];
    const widget = document.getElementById('portfolio-widget');
    const form = document.getElementById('portfolio-form');

    if (!pos || !currentPrice) {
        // Show "Ajouter position" compact button instead
        widget.style.display = 'flex';
        document.getElementById('pw-shares').textContent = 'Aucune position';
        document.getElementById('pw-pnl').textContent = '+ Ajouter';
        document.getElementById('pw-pnl').className = 'pw-pnl';
        return;
    }

    if (form.style.display === 'block') return; // Don't update while editing

    const pnl = (currentPrice - pos.avgPrice) * pos.shares;
    const pnlPct = ((currentPrice - pos.avgPrice) / pos.avgPrice * 100);
    const sign = pnl >= 0 ? '+' : '';

    widget.style.display = 'flex';
    document.getElementById('pw-shares').textContent = `${pos.shares} × @ ${pos.avgPrice.toFixed(2)}€`;
    const pnlEl = document.getElementById('pw-pnl');
    pnlEl.textContent = `${sign}${pnl.toFixed(2)}€ (${sign}${pnlPct.toFixed(1)}%)`;
    pnlEl.className = `pw-pnl ${pnl >= 0 ? 'pos' : 'neg'}`;
}

/* =================== ALERTS =================== */


function renderAlerts() {
    const list = document.getElementById('alert-list');
    list.innerHTML = '';
    if (STATE.alerts.length === 0) {
        list.innerHTML = '<p style="font-size:0.8rem;color:var(--text-3);text-align:center;padding:1rem;">Aucune alerte manuelle. Créez-en une ci-dessus.</p>';
        return;
    }
    STATE.alerts.forEach((alert, i) => {
        const div = document.createElement('div');
        div.className = `alert-item ${alert.triggered ? 'triggered' : ''}`;
        const asset = STATE.allAssets.find(a => a.isin === alert.isin);
        const assetName = asset ? asset.name : alert.isin;
        let condText = '';
        if (alert.type === 'above') condText = `Prix > ${alert.price} €`;
        else if (alert.type === 'below') condText = `Prix < ${alert.price} €`;
        else if (alert.type === 'change_up') condText = `Hausse > +${alert.price}%`;
        else if (alert.type === 'change_down') condText = `Baisse > -${alert.price}%`;
        div.innerHTML = `
            <div style="flex:1;">
                <strong style="font-size:0.82rem;">${assetName}</strong>
                <span style="color:var(--text-2);margin-left:8px;font-size:0.75rem;">${condText}</span>
                ${alert.triggered ? '<span style="color:var(--amber);font-size:0.7rem;display:block;margin-top:2px;">⚡ Déclenchée</span>' : ''}
            </div>
            <button class="alert-del" data-idx="${i}">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        `;
        div.querySelector('.alert-del').addEventListener('click', () => {
            STATE.alerts.splice(i, 1);
            localStorage.setItem('pea_alerts', JSON.stringify(STATE.alerts));
            renderAlerts();
        });
        list.appendChild(div);
    });
}

function populateAlertSelect() {
    const select = document.getElementById('alert-asset');
    if (!select) return;
    
    // Default option
    select.innerHTML = '<option value="">— Choisir un actif —</option>';
    
    if (STATE.favorites.length === 0) {
        const noFav = document.createElement('div');
        noFav.className = 'alert-no-favs';
        noFav.innerHTML = 'Vous devez d\'abord ajouter des favoris (⭐) pour pouvoir créer une alerte.';
        if (!select.nextElementSibling || !select.nextElementSibling.classList.contains('alert-no-favs')) {
            select.parentNode.insertBefore(noFav, select.nextSibling);
        }
        select.disabled = true;
        return;
    } else {
        select.disabled = false;
        const noFav = document.parentNode?.querySelector('.alert-no-favs');
        if (noFav) noFav.remove();
    }

    STATE.favorites.forEach(isin => {
        const asset = STATE.allAssets.find(a => a.isin === isin);
        const name = asset ? asset.name : isin;
        const opt = document.createElement('option');
        opt.value = isin;
        opt.textContent = `${name} (${isin})`;
        select.appendChild(opt);
    });
}

function checkAlerts(data) {
    let triggered = false;
    STATE.alerts.forEach(alert => {
        if (alert.isin !== data.isin || alert.triggered) return;
        if (alert.type === 'above' && data.price >= alert.price) { alert.triggered = true; triggered = true; }
        if (alert.type === 'below' && data.price <= alert.price) { alert.triggered = true; triggered = true; }
        if (alert.type === 'change_up' && data.change >= alert.price) { alert.triggered = true; triggered = true; }
        if (alert.type === 'change_down' && data.change <= -alert.price) { alert.triggered = true; triggered = true; }
    });
    if (triggered) {
        localStorage.setItem('pea_alerts', JSON.stringify(STATE.alerts));
        sendNotification(`⚡ Alerte PEA Déclenchée !`, `${data.name} à ${data.price.toFixed(2)} €`);
        showToast(`Alerte déclenchée : ${data.name} à ${data.price.toFixed(2)} €`, 'warn', 6000);
    }

    // AI Auto-detection: check if signal changed
    checkAiAutoAlert(data);
}

function checkAiAutoAlert(data) {
    const autoEnabled = document.getElementById('auto-alert-toggle')?.checked;
    if (!autoEnabled) return;
    if (!data.ai_status || !data.isin) return;

    const prevSignal = STATE.lastAiSignals[data.isin];
    STATE.lastAiSignals[data.isin] = data.ai_status;

    // Only alert if signal changed and it's a strong signal
    if (prevSignal && prevSignal !== data.ai_status) {
        const isStrong = data.ai_status.includes('ACHETER') || data.ai_status.includes('VENDRE');
        if (isStrong) {
            const isBuy = data.ai_status.includes('ACHETER');
            const msg = isBuy
                ? `${data.name} : Signal ACHETER détecté (RSI: ${data.rsi?.toFixed(0) || '?'})`
                : `${data.name} : Signal VENDRE détecté (RSI: ${data.rsi?.toFixed(0) || '?'})`;

            sendNotification(`🤖 Signal IA · ${data.name}`, msg);
            showToast(msg, isBuy ? 'success' : 'warn', 8000);
            addAutoAlertLog(data, isBuy);
        }
    }
}

function addAutoAlertLog(data, isBuy) {
    const log = JSON.parse(localStorage.getItem('pea_auto_alert_log') || '[]');
    const now = new Date();
    log.unshift({
        isin: data.isin,
        name: data.name,
        signal: data.ai_status,
        price: data.price,
        rsi: data.rsi,
        time: now.toISOString(),
        type: isBuy ? 'buy' : 'sell'
    });
    // Keep last 20 entries
    if (log.length > 20) log.length = 20;
    localStorage.setItem('pea_auto_alert_log', JSON.stringify(log));
    renderAutoAlertLog();
}

function renderAutoAlertLog() {
    const container = document.getElementById('auto-alert-log');
    if (!container) return;
    const log = JSON.parse(localStorage.getItem('pea_auto_alert_log') || '[]');
    if (log.length === 0) {
        container.innerHTML = '<p style="font-size:0.75rem;color:var(--text-3);text-align:center;padding:0.5rem;">Aucune alerte IA détectée pour le moment.</p>';
        return;
    }
    container.innerHTML = log.slice(0, 10).map(entry => {
        const d = new Date(entry.time);
        const timeStr = d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        return `<div class="auto-alert-entry ${entry.type}">
            <span class="aal-icon">${entry.type === 'buy' ? '📈' : '📉'}</span>
            <span class="aal-text"><strong>${entry.name}</strong> · ${entry.signal} · ${entry.price.toFixed(2)} € ${entry.rsi ? `(RSI ${entry.rsi.toFixed(0)})` : ''}</span>
            <span class="aal-time">${timeStr}</span>
        </div>`;
    }).join('');
}

function sendNotification(title, body) {
    if (localStorage.getItem('pea_notif_enabled') === 'false') return;
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, icon: './icon.png' });
    }
}

function loadAutoAlertToggle() {
    const toggle = document.getElementById('auto-alert-toggle');
    if (toggle) toggle.checked = localStorage.getItem('pea_auto_alerts') !== 'false';
    toggle?.addEventListener('change', (e) => {
        localStorage.setItem('pea_auto_alerts', e.target.checked ? 'true' : 'false');
    });
}

/* =================== CONTROLS SETUP =================== */
function setupControls() {
    // Timeframe buttons
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const tf = btn.getAttribute('data-tf');
            if (!tf) return; // Ignore le bouton "Comité de tendance" qui n'a pas de data-tf

            document.querySelectorAll('.tf-btn').forEach(b => {
                if (b.hasAttribute('data-tf')) b.classList.remove('active');
            });
            btn.classList.add('active');
            STATE.currentTimeframe = tf;
            await loadAssetDetail(STATE.currentIsin);
        });
    });

    // Volume toggle
    document.getElementById('show-volume').addEventListener('change', (e) => {
        document.getElementById('volume-panel').style.display = e.target.checked ? 'block' : 'none';
    });

    // VWAP toggle
    document.getElementById('show-vwap').addEventListener('change', () => {
        if (STATE.priceChart && STATE.priceChart.config.type !== 'candlestick') {
            STATE.priceChart.data.datasets[1].hidden = !document.getElementById('show-vwap').checked;
            rescaleYAxis();
        }
    });

    // SMA toggle
    const smaToggle = document.getElementById('show-sma');
    if (smaToggle) smaToggle.addEventListener('change', () => {
        if (STATE.priceChart && STATE.priceChart.config.type !== 'candlestick') {
            const show = smaToggle.checked;
            STATE.priceChart.data.datasets[2].hidden = !show;
            STATE.priceChart.data.datasets[3].hidden = !show;
            rescaleYAxis();
        }
    });

    // Bollinger toggle
    const bbToggle = document.getElementById('show-bb');
    if (bbToggle) bbToggle.addEventListener('change', () => {
        if (STATE.priceChart && STATE.priceChart.config.type !== 'candlestick') {
            const show = bbToggle.checked;
            STATE.priceChart.data.datasets[4].hidden = !show;
            STATE.priceChart.data.datasets[5].hidden = !show;
            rescaleYAxis();
        }
    });

    // Backtest Signals toggle
    const sigToggle = document.getElementById('show-signals');
    if (sigToggle) sigToggle.addEventListener('change', () => {
        if (STATE.priceChart && STATE.priceChart.config.type !== 'candlestick') {
            const show = sigToggle.checked;
            STATE.priceChart.data.datasets[6].hidden = !show;
            STATE.priceChart.data.datasets[7].hidden = !show;
            rescaleYAxis();
        }
    });

    // Chart Type buttons
    document.querySelectorAll('.ct-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.ct-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const type = btn.getAttribute('data-ct');
            switchChartType(type);
        });
    });

    // Search (debounced)
    document.getElementById('search-input').addEventListener('input', (e) => {
        clearTimeout(STATE.searchTimeout);
        STATE.searchTimeout = setTimeout(() => {
            const q = e.target.value.toLowerCase();
            const filtered = STATE.allAssets.filter(a => a.isin.toLowerCase().includes(q) || (a.name||'').toLowerCase().includes(q));
            renderScreener(filtered);
        }, 300);
    });

    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const f = btn.getAttribute('data-filter');
            let filtered = STATE.allAssets;
            if (f === 'up') filtered = filtered.filter(a => a.change >= 0);
            if (f === 'down') filtered = filtered.filter(a => a.change < 0);
            if (f === 'buy') filtered = filtered.filter(a => a.ai_status?.includes('ACHETER'));
            renderScreener(filtered);
        });
    });

    // Refresh scan
    document.getElementById('refresh-scan').addEventListener('click', async () => {
        const btn = document.getElementById('refresh-scan');
        btn.classList.add('spinning');
        try {
            const res = await fetch(`${API_URL}/scan`);
            if (res.ok) { STATE.allAssets = await res.json(); renderScreener(STATE.allAssets); }
        } catch(e) { console.warn(e); }
        setTimeout(() => btn.classList.remove('spinning'), 1000);
    });

    // Refresh opportunities
    const refreshOppBtn = document.getElementById('refresh-opp');
    if (refreshOppBtn) {
        refreshOppBtn.addEventListener('click', async () => {
            refreshOppBtn.classList.add('spinning');
            await fetchOpportunities();
            setTimeout(() => refreshOppBtn.classList.remove('spinning'), 1000);
        });
    }

    // Alert form
    document.getElementById('create-alert-btn').addEventListener('click', () => {
        const isin = document.getElementById('alert-asset').value.trim();
        const type = document.getElementById('alert-type').value;
        const price = parseFloat(document.getElementById('alert-price').value);
        if (!isin || isNaN(price)) return;
        STATE.alerts.push({ isin, type, price, triggered: false });
        localStorage.setItem('pea_alerts', JSON.stringify(STATE.alerts));
        renderAlerts();
        document.getElementById('alert-price').value = '';
    });

    // Settings form
    document.getElementById('save-settings-btn').addEventListener('click', () => {
        const urlParams = document.getElementById('setting-backend-url').value.trim();
        localStorage.setItem('pea_backend_url', urlParams);
        showToast('Paramètres sauvegardés. Rechargement...', 'success');
        setTimeout(() => window.location.reload(), 1000);
    });

    // Clear cache
    document.getElementById('btn-clear-cache')?.addEventListener('click', () => {
        if ('caches' in window) caches.keys().then(k => k.forEach(c => caches.delete(c)));
        showToast('Cache vidé avec succès', 'success');
    });

    // Reset app
    document.getElementById('btn-reset-app')?.addEventListener('click', () => {
        if (!confirm('Supprimer tous les favoris, alertes et paramètres ?')) return;
        localStorage.clear();
        if ('caches' in window) caches.keys().then(k => k.forEach(c => caches.delete(c)));
        window.location.reload();
    });

    // Notification toggle
    document.getElementById('setting-notif-enabled')?.addEventListener('change', (e) => {
        if (e.target.checked) {
            if ('Notification' in window && Notification.permission !== 'granted') {
                Notification.requestPermission().then(p => {
                    if (p !== 'granted') { e.target.checked = false; showToast('Notifications refusées par le navigateur', 'warn'); }
                    else { localStorage.setItem('pea_notif_enabled', 'true'); showToast('Notifications activées', 'success'); }
                });
            } else {
                localStorage.setItem('pea_notif_enabled', 'true');
            }
        } else {
            localStorage.setItem('pea_notif_enabled', 'false');
        }
    });

    // Auto-alerts toggle
    document.getElementById('setting-auto-alerts')?.addEventListener('change', (e) => {
        localStorage.setItem('pea_auto_alerts', e.target.checked ? 'true' : 'false');
        showToast(e.target.checked ? 'Alertes IA automatiques activées' : 'Alertes IA automatiques désactivées', 'info');
    });

    // Refresh interval
    document.getElementById('setting-refresh-interval')?.addEventListener('change', (e) => {
        localStorage.setItem('pea_refresh_interval', e.target.value);
        showToast(`Refresh réglé à ${e.target.value}s`, 'info');
    });

    // Default timeframe
    document.getElementById('setting-default-tf')?.addEventListener('change', (e) => {
        localStorage.setItem('pea_default_tf', e.target.value);
    });
}

function loadSettings() {
    document.getElementById('setting-backend-url').value = localStorage.getItem('pea_backend_url') || '';
    const notifEl = document.getElementById('setting-notif-enabled');
    if (notifEl) notifEl.checked = localStorage.getItem('pea_notif_enabled') === 'true' || ('Notification' in window && Notification.permission === 'granted');
    const autoEl = document.getElementById('setting-auto-alerts');
    if (autoEl) autoEl.checked = localStorage.getItem('pea_auto_alerts') !== 'false';
    const refreshEl = document.getElementById('setting-refresh-interval');
    if (refreshEl) refreshEl.value = localStorage.getItem('pea_refresh_interval') || '30';
    const tfEl = document.getElementById('setting-default-tf');
    if (tfEl) tfEl.value = localStorage.getItem('pea_default_tf') || '1d';
}

/* =================== NOTIFICATIONS =================== */
function requestNotification(data) {
    if (!('Notification' in window)) return showToast('Notifications non supportées.', 'warn');
    if (Notification.permission === 'granted') {
        sendNotification(`PEA IA · ${data.name}`, `${data.price.toFixed(2)} € | Signal: ${data.ai_status}`);
        showToast('Notification envoyée', 'success');
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(p => {
            if (p === 'granted') requestNotification(data);
            else showToast('Notifications refusées', 'warn');
        });
    }
}

/* =================== HELPERS =================== */
function formatVolume(v) {
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
    if (v >= 1_000) return (v / 1_000).toFixed(0) + 'K';
    return v?.toString() || '--';
}

/* =================== MOCK DATA (Mode hors-ligne) =================== */
function getMockAssets() {
    return [
        { isin: 'FR0013341781', name: '2CRSI S.A.', price: 39.70, change: -4.15, trend: 'down', ai_status: 'VENDRE' },
        { isin: 'FR0000121014', name: 'LVMH', price: 598.50, change: 1.15, trend: 'up', ai_status: 'GARDER' },
        { isin: 'FR0000120271', name: 'TotalEnergies', price: 56.20, change: -0.85, trend: 'down', ai_status: 'GARDER' },
        { isin: 'FR0000131104', name: 'BNP Paribas', price: 63.10, change: 2.40, trend: 'up', ai_status: 'ACHETER FORT' },
        { isin: 'FR0000120578', name: 'Sanofi', price: 92.30, change: -0.30, trend: 'down', ai_status: 'GARDER' },
        { isin: 'FR0000120073', name: 'Air Liquide', price: 168.50, change: 0.45, trend: 'up', ai_status: 'GARDER' },
        { isin: 'FR0011550185', name: 'Amundi S&P 500', price: 615.10, change: -0.45, trend: 'down', ai_status: 'GARDER' },
        { isin: 'FR0013412020', name: 'Amundi Nasdaq', price: 1045.20, change: 2.10, trend: 'up', ai_status: 'ACHETER FORT' },
    ];
}

function getMockDetail(isin) {
    const base = getMockAssets().find(a => a.isin === isin) || getMockAssets()[0];
    const labels = ['09h00','09h30','10h00','10h30','11h00','11h30','12h00','12h30','13h00','13h30','14h00','14h30','15h00','15h30'];

    let price = base.price + (base.change > 0 ? -1.5 : 1.5);
    const dataseries = labels.map((_, i) => {
        price += (Math.random() - 0.5) * (base.price * 0.008);
        return Math.max(0.1, parseFloat(price.toFixed(2)));
    });

    const vwapSeries = dataseries.map((p, i) => {
        const slice = dataseries.slice(0, i + 1);
        return parseFloat((slice.reduce((a, b) => a + b, 0) / slice.length).toFixed(2));
    });

    const volumeSeries = labels.map(() => Math.floor(Math.random() * 50000 + 5000));
    const rsi = base.change < -3 ? 28 : base.change > 3 ? 72 : 45 + Math.random() * 20;
    const macd = base.change > 0 ? 0.3 + Math.random() : -0.3 - Math.random();

    return {
        ...base,
        ticker: 'AL2SI.PA',
        labels,
        dataseries,
        vwapSeries,
        volumeSeries,
        rsi: parseFloat(rsi.toFixed(1)),
        macd: parseFloat(macd.toFixed(2)),
        vwap_signal_pct: dataseries[dataseries.length - 1] > vwapSeries[vwapSeries.length - 1] ? 65 : 35,
        high52: base.price * 1.25,
        low52: base.price * 0.75,
    };
}

function getMockOpportunities() {
    return [
        { isin: 'FR0013341781', name: '2CRSI S.A.', price: 38.92, change: -5.94, score: 75,
          label: 'FORTE OPPORTUNITÉ', rsi: 22.5,
          reasons: ["RSI extrêmement survendu (22)", "Prix proche du bas 52 semaines (5% au-dessus)", "Volume ×2.3 (accumulation institutionnelle)"],
          low52: 37.10, high52: 54.00 },
        { isin: 'FR0000120271', name: 'TotalEnergies', price: 55.10, change: -5.25, score: 50,
          label: 'OPPORTUNITÉ', rsi: 38.2,
          reasons: ["RSI survendu (38)", "MACD croisement haussier", "Zone basse annuelle"],
          low52: 48.50, high52: 72.00 },
        { isin: 'FR0000125007', name: 'Saint-Gobain', price: 81.44, change: 4.57, score: 25,
          label: 'À SURVEILLER', rsi: 45.0,
          reasons: ["RSI en zone d'opportunité (45)"],
          low52: 58.00, high52: 92.00 },
    ];
}
