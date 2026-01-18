/**
 * Riftech Security System - Main Application JavaScript
 * Handles all frontend interactions, WebSocket, and API calls
 */

// ========== GLOBAL VARIABLES ==========
let ws = null;
let wsReconnectAttempts = 0;
let wsMaxReconnectAttempts = 5;
let wsReconnectDelay = 5000;
let token = localStorage.getItem('token');
let currentZonePoints = [];

// Streaming variables
let streamRetryCount = 0;
let maxStreamRetries = 3;
let streamRetryDelay = 2000;
let streamLatencyStart = 0;
let streamLatency = 0;
let streamLastUpdate = Date.now();

// ========== INITIALIZATION ==========

document.addEventListener('DOMContentLoaded', () => {
    // Check authentication
    if (!token) {
        window.location.href = '/';
        return;
    }
    
    // Initialize app
    initApp();
});

async function initApp() {
    // Set username
    const username = localStorage.getItem('username');
    if (username) {
        document.getElementById('username').textContent = username;
    }
    
    // Initialize tabs
    initTabs();
    
    // Initialize subtabs
    initSubTabs();
    
    // Initialize mode buttons
    initModeButtons();
    
    // Initialize zone editor
    initZoneEditor();
    
    // Connect WebSocket
    connectWebSocket();
    
    // Load initial data
    await loadStats();
    await loadConfig();
    await loadZones();
    await loadFaces();
    await loadAlerts();
    
    // Start periodic updates
    setInterval(updateStats, 1000);
    
    // Initialize streaming
    initStream();
}

// ========== TABS ==========

function initTabs() {
    const tabs = document.querySelectorAll('[data-tab]');
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remove active from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active to clicked tab
            tab.classList.add('active');
            const tabId = tab.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
            
            // Update URL hash
            window.location.hash = tabId;
        });
    });
    
    // Check URL hash on load
    const hash = window.location.hash.substring(1);
    if (hash && document.getElementById(hash)) {
        document.querySelector(`[data-tab="${hash}"]`).click();
    }
}

function initSubTabs() {
    const tabs = document.querySelectorAll('[data-subtab]');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.subtab-content').forEach(c => c.classList.remove('active'));
            
            // Add active to clicked tab
            tab.classList.add('active');
            const subtabId = tab.getAttribute('data-subtab');
            document.getElementById(subtabId).classList.add('active');
        });
    });
}

// ========== MODE BUTTONS ==========

function initModeButtons() {
    const modeButtons = document.querySelectorAll('[data-mode]');
    modeButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const mode = btn.getAttribute('data-mode');
            await setMode(mode);
        });
    });
}

async function setMode(mode) {
    try {
        const response = await fetch('/api/mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ mode })
        });
        
        if (response.ok) {
            updateModeUI(mode);
        } else {
            console.error('Failed to set mode:', await response.text());
        }
    } catch (error) {
        console.error('Error setting mode:', error);
    }
}

function updateModeUI(mode) {
    // Update current mode display
    document.getElementById('currentMode').textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
    
    // Update button states
    document.querySelectorAll('[data-mode]').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-mode') === mode) {
            btn.classList.add('active');
        }
    });
}

// ========== WEBSOCKET ==========

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        wsReconnectAttempts = 0;
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        attemptReconnect();
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function attemptReconnect() {
    if (wsReconnectAttempts < wsMaxReconnectAttempts) {
        wsReconnectAttempts++;
        console.log(`Attempting to reconnect (${wsReconnectAttempts}/${wsMaxReconnectAttempts})...`);
        
        setTimeout(() => {
            connectWebSocket();
        }, wsReconnectDelay);
    }
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'detection_update':
            updateStatsUI(message.stats);
            break;
        case 'mode_change':
            updateModeUI(message.mode);
            break;
        case 'alert':
            handleAlert(message);
            break;
        case 'echo':
            console.log('Echo from server:', message.message);
            break;
        default:
            console.log('Unknown message type:', message.type);
    }
}

function handleAlert(message) {
    // Show alert notification
    const alertsList = document.getElementById('recentAlerts');
    const alertHtml = `
        <div class="alert-item">
            <img src="${message.photo || '/static/images/alert-placeholder.png'}" alt="Alert">
            <div class="alert-info">
                <div class="alert-time">${new Date(message.timestamp).toLocaleString()}</div>
                <div class="alert-message">${message.message}</div>
            </div>
        </div>
    `;
    
    // Remove "No recent alerts" message if exists
    if (alertsList.querySelector('.text-muted')) {
        alertsList.innerHTML = '';
    }
    
    // Add new alert at the top
    alertsList.insertAdjacentHTML('afterbegin', alertHtml);
    
    // Keep only last 10 alerts
    const alerts = alertsList.querySelectorAll('.alert-item');
    if (alerts.length > 10) {
        alerts[alerts.length - 1].remove();
    }
}

// ========== API CALLS ==========

async function apiCall(endpoint, options = {}) {
    const defaultOptions = {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    if (mergedOptions.body && typeof mergedOptions.body === 'object') {
        mergedOptions.headers['Content-Type'] = 'application/json';
        mergedOptions.body = JSON.stringify(mergedOptions.body);
    }
    
    try {
        const response = await fetch(endpoint, mergedOptions);
        
        if (response.status === 401) {
            // Unauthorized - redirect to login
            localStorage.removeItem('token');
            localStorage.removeItem('username');
            window.location.href = '/';
            return null;
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call error:', error);
        return null;
    }
}

// ========== STATS ==========

async function loadStats() {
    const stats = await apiCall('/api/stats');
    if (stats) {
        updateStatsUI(stats);
    }
}

async function updateStats() {
    const stats = await apiCall('/api/stats');
    if (stats) {
        updateStatsUI(stats);
    }
}

function updateStatsUI(stats) {
    // Format FPS to 2 decimal places if it's a number, otherwise 0
    const fps = typeof stats.fps === 'number' ? stats.fps.toFixed(2) : '0';
    
    document.getElementById('fps').textContent = fps;
    document.getElementById('persons').textContent = stats.persons || 0;
    document.getElementById('trusted').textContent = stats.trusted || 0;
    document.getElementById('unknown').textContent = stats.unknown || 0;
    document.getElementById('breaches').textContent = stats.breaches || 0;
    document.getElementById('videoFps').textContent = fps;
}

// ========== CONFIGURATION ==========

async function loadConfig() {
    const config = await apiCall('/api/config');
    if (config) {
        populateConfig(config);
    }
}

function populateConfig(config) {
    // Camera settings
    document.getElementById('cameraType').value = config.camera.type;
    document.getElementById('rtspUrl').value = config.camera.rtsp_url || '';
    document.getElementById('cameraId').value = config.camera.camera_id || 0;
    document.getElementById('width').value = config.camera.width || 1280;
    document.getElementById('height').value = config.camera.height || 720;
    document.getElementById('fps').value = config.camera.fps || 15;
    document.getElementById('detectFps').value = config.camera.detect_fps || 5;
    
    // Detection settings
    document.getElementById('yoloConfidence').value = config.detection.yolo_confidence || 0.20;
    document.getElementById('yoloConfValue').textContent = config.detection.yolo_confidence || 0.20;
    document.getElementById('yoloModel').value = config.detection.yolo_model || 'yolov8n.pt';
    document.getElementById('faceTolerance').value = config.detection.face_tolerance || 0.6;
    document.getElementById('faceTolValue').textContent = config.detection.face_tolerance || 0.6;
    document.getElementById('motionThreshold').value = config.detection.motion_threshold || 15;
    document.getElementById('motionThreshValue').textContent = config.detection.motion_threshold || 15;
    document.getElementById('motionMinArea').value = config.detection.motion_min_area || 500;
    document.getElementById('motionAreaValue').textContent = config.detection.motion_min_area || 500;
    document.getElementById('skeletonEnabled').checked = config.detection.skeleton_enabled !== false;
    
    // Alert settings
    document.getElementById('telegramEnabled').checked = config.alerts.telegram_enabled || false;
    document.getElementById('telegramBotToken').value = config.alerts.telegram_bot_token || '';
    document.getElementById('telegramChatId').value = config.alerts.telegram_chat_id || '';
    document.getElementById('cooldownSeconds').value = config.alerts.cooldown_seconds || 5;
    document.getElementById('snapshotOnAlert').checked = config.alerts.snapshot_on_alert !== false;
    
    // System settings
    document.getElementById('defaultMode').value = config.system.default_mode || 'normal';
    document.getElementById('enableGpu').checked = config.system.enable_gpu !== false;
    document.getElementById('threadCount').value = config.system.thread_count || 4;
    document.getElementById('logLevel').value = config.system.log_level || 'INFO';
    
    // Update resolution display
    document.getElementById('resolution').textContent = 
        `${config.camera.width || 1280}x${config.camera.height || 720}`;
}

async function saveConfig() {
    const config = {
        // Camera settings
        camera_type: document.getElementById('cameraType').value,
        rtsp_url: document.getElementById('rtspUrl').value,
        camera_id: parseInt(document.getElementById('cameraId').value),
        width: parseInt(document.getElementById('width').value),
        height: parseInt(document.getElementById('height').value),
        fps: parseInt(document.getElementById('fps').value),
        detect_fps: parseInt(document.getElementById('detectFps').value),
        
        // Detection settings
        yolo_confidence: parseFloat(document.getElementById('yoloConfidence').value),
        yolo_model: document.getElementById('yoloModel').value,
        face_tolerance: parseFloat(document.getElementById('faceTolerance').value),
        motion_threshold: parseInt(document.getElementById('motionThreshold').value),
        motion_min_area: parseInt(document.getElementById('motionMinArea').value),
        skeleton_enabled: document.getElementById('skeletonEnabled').checked,
        
        // Alert settings
        telegram_enabled: document.getElementById('telegramEnabled').checked,
        telegram_bot_token: document.getElementById('telegramBotToken').value,
        telegram_chat_id: document.getElementById('telegramChatId').value,
        cooldown_seconds: parseInt(document.getElementById('cooldownSeconds').value),
        snapshot_on_alert: document.getElementById('snapshotOnAlert').checked,
        
        // System settings
        default_mode: document.getElementById('defaultMode').value,
        enable_gpu: document.getElementById('enableGpu').checked,
        thread_count: parseInt(document.getElementById('threadCount').value),
        log_level: document.getElementById('logLevel').value
    };
    
    const result = await apiCall('/api/config', {
        method: 'POST',
        body: config
    });
    
    if (result) {
        alert('Configuration saved successfully!');
    }
}

// ========== ZONES ==========

function initZoneEditor() {
    const canvas = document.getElementById('zoneCanvas');
    const container = document.querySelector('.video-container');
    
    // Set canvas size
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    
    // Handle clicks
    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = Math.round((e.clientX - rect.left) * (canvas.width / rect.width));
        const y = Math.round((e.clientY - rect.top) * (canvas.height / rect.height));
        
        currentZonePoints.push([x, y]);
        drawZones();
    });
    
    // Handle resize
    window.addEventListener('resize', () => {
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
        drawZones();
    });
    
    // Draw zones periodically
    setInterval(drawZones, 1000);
}

async function loadZones() {
    const data = await apiCall('/api/zones');
    if (data && data.zones) {
        displayZones(data.zones);
    }
}

function displayZones(zones) {
    const zonesList = document.getElementById('zonesList');
    
    if (zones.length === 0) {
        zonesList.innerHTML = '<p class="text-muted">No zones defined</p>';
        return;
    }
    
    zonesList.innerHTML = zones.map(zone => `
        <div class="zone-item">
            <div class="zone-name">${zone.name || `Zone ${zone.id}`}</div>
            <span class="zone-status ${zone.armed ? 'zone-armed' : 'zone-disarmed'}">
                ${zone.armed ? 'Armed' : 'Disarmed'}
            </span>
            <div style="margin-top: 10px;">
                <button class="btn btn-secondary btn-sm" onclick="toggleZone(${zone.id})">
                    ${zone.armed ? 'Disarm' : 'Arm'}
                </button>
                <button class="btn btn-danger btn-sm" onclick="deleteZone(${zone.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

function drawZones() {
    const canvas = document.getElementById('zoneCanvas');
    const ctx = canvas.getContext('2d');
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw current zone being created
    if (currentZonePoints.length > 0) {
        ctx.strokeStyle = '#ffff00';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(currentZonePoints[0][0], currentZonePoints[0][1]);
        
        for (let i = 1; i < currentZonePoints.length; i++) {
            ctx.lineTo(currentZonePoints[i][0], currentZonePoints[i][1]);
        }
        
        ctx.stroke();
        
        // Draw points
        currentZonePoints.forEach(point => {
            ctx.fillStyle = '#ffff00';
            ctx.beginPath();
            ctx.arc(point[0], point[1], 5, 0, Math.PI * 2);
            ctx.fill();
        });
    }
    
    // Update points display
    const zonePointsDiv = document.getElementById('zonePoints');
    if (currentZonePoints.length > 0) {
        zonePointsDiv.innerHTML = `Points: ${currentZonePoints.map(p => `(${p[0]}, ${p[1]})`).join(' ')}<br>Click to add more points`;
    } else {
        zonePointsDiv.innerHTML = 'Click on video to define zone points (minimum 3 points)';
    }
}

async function saveZone() {
    const name = document.getElementById('zoneName').value.trim();
    const armed = document.getElementById('zoneArmed').checked;
    
    if (currentZonePoints.length < 3) {
        alert('Please define at least 3 points for the zone');
        return;
    }
    
    const result = await apiCall('/api/zones', {
        method: 'POST',
        body: {
            name,
            armed,
            points: currentZonePoints
        }
    });
    
    if (result) {
        alert('Zone created successfully!');
        clearZoneEditor();
        await loadZones();
    }
}

async function toggleZone(zoneId) {
    // Toggle zone armed status
    await loadZones(); // Reload to get current state
}

async function deleteZone(zoneId) {
    if (!confirm('Are you sure you want to delete this zone?')) {
        return;
    }
    
    const result = await apiCall(`/api/zones/${zoneId}`, {
        method: 'DELETE'
    });
    
    if (result) {
        alert('Zone deleted successfully!');
        await loadZones();
    }
}

async function clearAllZones() {
    if (!confirm('Are you sure you want to delete all zones?')) {
        return;
    }
    
    const result = await apiCall('/api/zones', {
        method: 'DELETE'
    });
    
    if (result) {
        alert('All zones cleared!');
        await loadZones();
    }
}

function clearZoneEditor() {
    currentZonePoints = [];
    document.getElementById('zoneName').value = '';
    drawZones();
}

// ========== FACES ==========

async function loadFaces() {
    const data = await apiCall('/api/faces');
    if (data && data.faces) {
        displayFaces(data.faces);
    }
}

function displayFaces(faces) {
    const facesList = document.getElementById('facesList');
    
    if (faces.length === 0) {
        facesList.innerHTML = '<p class="text-muted">No trusted faces</p>';
        return;
    }
    
    facesList.innerHTML = faces.map(face => `
        <div class="face-item">
            <img src="/api/faces/${face.name}/image" alt="${face.name}" onerror="this.src='/static/images/face-placeholder.png'">
            <div class="face-info">
                <div class="face-name">${face.name}</div>
            </div>
            <button class="btn btn-danger btn-sm" onclick="deleteFace('${face.name}')">Delete</button>
        </div>
    `).join('');
}

async function uploadFace() {
    const fileInput = document.getElementById('faceUpload');
    const file = fileInput.files[0];
    
    if (!file) {
        return;
    }
    
    const name = prompt('Enter name for this face:');
    if (!name || !name.trim()) {
        alert('Please enter a name for the face');
        return;
    }
    
    const formData = new FormData();
    formData.append('name', name.trim());
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/faces/upload', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        if (response.ok) {
            alert('Face uploaded successfully!');
            await loadFaces();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to upload face');
        }
    } catch (error) {
        console.error('Error uploading face:', error);
        alert('Error uploading face');
    }
    
    // Clear file input
    fileInput.value = '';
}

async function deleteFace(faceName) {
    if (!confirm(`Are you sure you want to delete ${faceName}?`)) {
        return;
    }
    
    const result = await apiCall(`/api/faces/${faceName}`, {
        method: 'DELETE'
    });
    
    if (result) {
        alert('Face deleted successfully!');
        await loadFaces();
    }
}

// ========== ALERTS ==========

async function loadAlerts() {
    const data = await apiCall('/api/alerts');
    if (data && data.alerts) {
        displayAlerts(data.alerts);
    }
}

function displayAlerts(alerts) {
    const alertsList = document.getElementById('alertsList');
    
    if (alerts.length === 0) {
        alertsList.innerHTML = '<p class="text-muted">No alerts</p>';
        return;
    }
    
    alertsList.innerHTML = alerts.map(alert => `
        <div class="alert-item">
            <img src="/api/alerts/${alert.filename}" alt="Alert" onerror="this.src='/static/images/alert-placeholder.png'">
            <div class="alert-info">
                <div class="alert-time">${new Date(alert.timestamp).toLocaleString()}</div>
                <div class="alert-message">Security Alert</div>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="viewAlert('${alert.filename}')">View</button>
        </div>
    `).join('');
}

function viewAlert(filename) {
    window.open(`/api/alerts/${filename}`, '_blank');
}

// ========== SNAPSHOT ==========

async function captureSnapshot() {
    try {
        const response = await fetch('/api/snapshot', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            alert('Snapshot captured successfully!');
        } else {
            alert('Failed to capture snapshot');
        }
    } catch (error) {
        console.error('Error capturing snapshot:', error);
        alert('Error capturing snapshot');
    }
}

// ========== LOGOUT ==========

async function logout() {
    await apiCall('/api/auth/logout', {
        method: 'POST'
    });
    
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    window.location.href = '/';
}

// ========== STREAMING FUNCTIONS ==========

function initStream() {
    updateStreamSettings();
}

function updateStreamSettings() {
    // Get current settings
    const fps = document.getElementById('streamFps').value;
    const quality = document.getElementById('streamQuality').value;
    const height = document.getElementById('streamHeight').value;
    const showBbox = document.getElementById('showBbox').checked;
    const showTimestamp = document.getElementById('showTimestamp').checked;
    const showZones = document.getElementById('showZones').checked;
    
    // Build stream URL with parameters
    const videoStream = document.getElementById('videoStream');
    const params = new URLSearchParams({
        fps: fps,
        quality: quality,
        height: height,
        bbox: showBbox ? '1' : '0',
        timestamp: showTimestamp ? '1' : '0',
        zones: showZones ? '1' : '0'
    });
    
    // Update stream URL
    const newSrc = `/api/stream?${params.toString()}`;
    
    // Only update if URL changed
    if (videoStream.src !== newSrc) {
        videoStream.src = newSrc;
        updateStreamStatus('Connecting...', 'text-yellow');
    }
}

function refreshStream() {
    const videoStream = document.getElementById('videoStream');
    
    // Show loading
    showStreamLoading(true);
    hideStreamError();
    
    // Force reload by adding timestamp
    const currentSrc = new URL(videoStream.src, window.location.origin);
    currentSrc.searchParams.set('t', Date.now());
    
    // Reset retry count
    streamRetryCount = 0;
    
    // Update source
    videoStream.src = currentSrc.toString();
    
    // Update status
    updateStreamStatus('Refreshing...', 'text-yellow');
}

function onStreamLoaded() {
    // Hide loading
    showStreamLoading(false);
    hideStreamError();
    
    // Update status
    updateStreamStatus('Connected', 'text-green');
    
    // Reset retry count
    streamRetryCount = 0;
    
    // Update latency
    if (streamLatencyStart > 0) {
        streamLatency = Date.now() - streamLatencyStart;
        document.getElementById('streamLatency').textContent = `${streamLatency}ms`;
        streamLatencyStart = 0;
    }
    
    // Update last update time
    streamLastUpdate = Date.now();
    
    console.log('Stream loaded successfully');
}

function onStreamError() {
    console.error('Stream error occurred');
    
    // Increment retry count
    streamRetryCount++;
    
    if (streamRetryCount <= maxStreamRetries) {
        // Show loading and retry
        showStreamLoading(true);
        updateStreamStatus(`Reconnecting (${streamRetryCount}/${maxStreamRetries})...`, 'text-yellow');
        
        // Retry after delay
        setTimeout(() => {
            refreshStream();
        }, streamRetryDelay);
    } else {
        // Max retries reached, show error
        showStreamLoading(false);
        showStreamError();
        updateStreamStatus('Offline', 'text-red');
    }
}

function showStreamLoading(show) {
    const loadingElement = document.getElementById('streamLoading');
    if (loadingElement) {
        loadingElement.style.display = show ? 'block' : 'none';
    }
}

function hideStreamLoading() {
    showStreamLoading(false);
}

function showStreamError() {
    const errorElement = document.getElementById('streamError');
    if (errorElement) {
        errorElement.style.display = 'block';
    }
}

function hideStreamError() {
    const errorElement = document.getElementById('streamError');
    if (errorElement) {
        errorElement.style.display = 'none';
    }
}

function updateStreamStatus(status, colorClass) {
    const statusElement = document.getElementById('streamStatus');
    if (statusElement) {
        statusElement.textContent = status;
        statusElement.className = colorClass;
    }
}

// ========== UTILITY FUNCTIONS ==========

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const mainContent = document.querySelector('.main-content');
    mainContent.insertBefore(alertDiv, mainContent.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}
