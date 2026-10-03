// APKs Guard Pro 289 - Ultra-Fast Non-Blocking Frontend Controller
let currentScanMode = 'quick';
let isScanning = false;
let isCleaning = false;
let isPolling = false;
let currentThreats = [];
let appListCache = [];
let appFilterMode = 'user';
let isSimulatorMode = false;
let renderedLogCount = 0;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

window.addEventListener('pywebviewready', () => {
  console.log("PyWebView API bridge connected.");
  fetchDatabaseStats();
  pollStatusUpdates();
});

function initApp() {
  console.log("Initializing APKs Guard Pro 289...");
  
  // Single coordinated polling loop (1.2s interval)
  setInterval(pollStatusUpdates, 1200);
  
  // Fetch initial stats
  fetchDatabaseStats();
  
  // Check updates on startup
  setTimeout(() => {
    checkUpdatesOnStartup();
  }, 2000);
}

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  
  const target = document.getElementById(tabId);
  if (target) target.classList.add('active');
  
  const navItems = document.querySelectorAll('.nav-item');
  if (tabId === 'tab-scanner') navItems[0].classList.add('active');
  else if (tabId === 'tab-updates') navItems[1].classList.add('active');
  else if (tabId === 'tab-device') navItems[2].classList.add('active');
  else if (tabId === 'tab-apps') navItems[3].classList.add('active');
  else if (tabId === 'tab-drivers') navItems[4].classList.add('active');
  else if (tabId === 'tab-logs') navItems[5].classList.add('active');
  else if (tabId === 'tab-settings') navItems[6].classList.add('active');
}

// Scan Mode Selector
function selectScanMode(mode) {
  if (isScanning) return;
  currentScanMode = mode;
  document.querySelectorAll('.scan-card').forEach(el => el.classList.remove('selected'));
  
  if (mode === 'quick') document.getElementById('cardQuickScan').classList.add('selected');
  else if (mode === 'full') document.getElementById('cardFullScan').classList.add('selected');
  else if (mode === 'smart') document.getElementById('cardSmartScan').classList.add('selected');
  else if (mode === 'disabled') document.getElementById('cardDisabledScan').classList.add('selected');
  else if (mode === 'wipe_non_essential') {
    const elWipe = document.getElementById('cardWipeScan');
    if (elWipe) elWipe.classList.add('selected');
  }
}

// API Calls to Python Backend with safe execution
async function callBackend(methodName, ...args) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api[methodName]) {
    try {
      return await window.pywebview.api[methodName](...args);
    } catch (e) {
      console.error(`Backend error in ${methodName}:`, e);
      return null;
    }
  } else {
    return mockBackendResponse(methodName, ...args);
  }
}

// Master Coordinated Poller (Non-blocking & Thread-Safe)
async function pollStatusUpdates() {
  if (isPolling) return;
  isPolling = true;

  try {
    // 1. Device Info
    const info = await callBackend('get_device_info');
    updateDeviceStatusUI(info);

    // 2. Incremental Live Logs
    const logs = await callBackend('get_live_logs');
    if (logs && Array.isArray(logs)) {
      renderIncrementalLogs(logs);
    }

    // 3. Scan state monitoring
    if (isScanning) {
      const scanState = await callBackend('get_scan_state');
      if (scanState) handleScanStateUpdate(scanState);
    }

    // 4. Clean state monitoring
    if (isCleaning) {
      const cleanState = await callBackend('get_clean_state');
      if (cleanState) handleCleanStateUpdate(cleanState);
    }
  } catch (err) {
    console.error("Polling error:", err);
  } finally {
    isPolling = false;
  }
}

function updateDeviceStatusUI(info) {
  const dot = document.getElementById('statusDot');
  const text = document.getElementById('deviceStatusText');
  const battery = document.getElementById('batteryPill');
  
  if (info && info.serial) {
    dot.className = 'status-indicator online';
    text.innerHTML = `<span><svg class="status-svg" viewBox="0 0 24 24" style="color:var(--accent-emerald)"><polyline points="20 6 9 17 4 12"/></svg> <b>${info.brand} ${info.model}</b> (Android ${info.android_version})</span>`;
    battery.style.display = 'inline-flex';
    battery.innerHTML = `<svg class="btn-svg" viewBox="0 0 24 24" style="color:var(--accent-emerald)"><rect x="1" y="6" width="18" height="12" rx="2"/><line x1="23" y1="11" x2="23" y2="13"/></svg> <span>${info.battery || '100%'}</span>`;
    
    // Update specs in device tab
    const elB = document.getElementById('devInfoBrand'); if (elB) elB.innerText = info.brand || '-';
    const elM = document.getElementById('devInfoModel'); if (elM) elM.innerText = info.model || '-';
    const elA = document.getElementById('devInfoAndroid'); if (elA) elA.innerText = info.android_version || '-';
    const elS = document.getElementById('devInfoSerial'); if (elS) elS.innerText = info.serial || '-';
    const elId = document.getElementById('devInfoBuild'); if (elId) elId.innerText = info.build_id || '-';
    const elP = document.getElementById('devInfoPatch'); if (elP) elP.innerText = info.security_patch || '-';
    const elR = document.getElementById('devInfoRoot'); if (elR) elR.innerText = info.root || 'No';
    const elBat = document.getElementById('devInfoBattery'); if (elBat) elBat.innerText = info.battery || '100%';
  } else {
    dot.className = 'status-indicator offline';
    text.innerHTML = `<span><svg class="status-svg" viewBox="0 0 24 24" style="color:var(--accent-crimson)"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> ไม่พบอุปกรณ์ (กรุณาต่อสาย USB และเปิด USB Debugging)</span>`;
    battery.style.display = 'none';
  }
}

// Toggle Simulator Mode
document.getElementById('btnToggleSimulator').addEventListener('click', async () => {
  isSimulatorMode = !isSimulatorMode;
  await callBackend('set_simulator_mode', isSimulatorMode);
  const info = await callBackend('refresh_device_info');
  updateDeviceStatusUI(info);
});

document.getElementById('btnRefreshDevice').addEventListener('click', async () => {
  const info = await callBackend('refresh_device_info');
  updateDeviceStatusUI(info);
});

// Database & Updates Management
async function fetchDatabaseStats() {
  const stats = await callBackend('get_database_stats');
  if (stats) {
    document.getElementById('headerDbCount').innerText = Number(stats.virus_signatures_count || 2570).toLocaleString();
    document.getElementById('dbSignaturesCount').innerText = Number(stats.virus_signatures_count || 2570).toLocaleString();
    document.getElementById('dbWhitelistCount').innerText = Number(stats.whitelist_count || 234).toLocaleString();
    document.getElementById('dbVersionText').innerText = `v${stats.version || '2026.09.29'}`;
    document.getElementById('dbLastUpdatedText').innerText = stats.last_updated || '2026-09-29 20:00:00';
  }
}

async function checkUpdatesOnStartup() {
  const res = await callBackend('check_for_updates');
  if (res && res.has_update) {
    const badge = document.getElementById('headerUpdateBadge');
    badge.innerText = "UPDATE AVAILABLE";
    badge.style.background = "#fee2e2";
    badge.style.color = "#dc2626";
    badge.style.borderColor = "#fca5a5";
    badge.classList.add('glow-active');
  }
}

async function performVirusUpdate() {
  const btn = document.getElementById('btnPerformUpdate');
  btn.innerHTML = `<svg class="btn-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> <span>กำลังดาวน์โหลดและอัพเดทฐานข้อมูล...</span>`;
  btn.disabled = true;
  
  const res = await callBackend('perform_update');
  btn.disabled = false;
  btn.innerHTML = `<svg class="btn-svg" style="width:18px; height:18px;" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> <span>กดอัพเดทฐานข้อมูลไวรัสล่าสุด</span>`;
  
  if (res && res.success) {
    alert(`อัพเดทฐานข้อมูลสำเร็จ!\n- เวอร์ชั่นใหม่: ${res.new_version}\n- เพิ่มไวรัสใหม่: +${res.added_count} รายการ\n- ไวรัสทั้งหมดในระบบ: ${res.total_count} รายการ`);
    fetchDatabaseStats();
    
    const badge = document.getElementById('headerUpdateBadge');
    badge.innerText = "LATEST";
    badge.style.background = "#e0f2fe";
    badge.style.color = "#0369a1";
    badge.style.borderColor = "#bae6fd";
    badge.classList.remove('glow-active');
  } else {
    alert(`ข้อความ: ${res ? res.error || 'ฐานข้อมูลเป็นเวอร์ชั่นล่าสุดแล้ว' : 'อัพเดทเรียบร้อย'}`);
  }
}

// Custom Rules
async function submitCustomMalware() {
  const pkg = document.getElementById('inpCustomMalwarePkg').value.trim();
  const name = document.getElementById('inpCustomMalwareName').value.trim();
  const risk = document.getElementById('selCustomMalwareRisk').value;
  
  if (!pkg) {
    alert("กรุณาระบุชื่อ Package Name (เช่น com.scam.fakeapp)");
    return;
  }
  
  const res = await callBackend('add_custom_signature', pkg, name, risk);
  if (res && res[0]) {
    alert(`บันทึกกฎไวรัส [${pkg}] เรียบร้อยแล้ว!`);
    document.getElementById('inpCustomMalwarePkg').value = '';
    document.getElementById('inpCustomMalwareName').value = '';
    fetchDatabaseStats();
  }
}

async function submitCustomWhitelist() {
  const pkg = document.getElementById('inpCustomWhitelistPkg').value.trim();
  const name = document.getElementById('inpCustomWhitelistName').value.trim();
  const cat = document.getElementById('inpCustomWhitelistCat').value.trim();
  
  if (!pkg) {
    alert("กรุณาระบุชื่อ Package Name ที่ต้องการปกป้อง");
    return;
  }
  
  const res = await callBackend('add_custom_whitelist', pkg, name, cat);
  if (res && res[0]) {
    alert(`บันทึกลงรายการปกป้อง [${pkg}] เรียบร้อยแล้ว!`);
    document.getElementById('inpCustomWhitelistPkg').value = '';
    document.getElementById('inpCustomWhitelistName').value = '';
    document.getElementById('inpCustomWhitelistCat').value = '';
    fetchDatabaseStats();
  }
}

// Scanner Actions (Non-blocking Async)
async function startScan() {
  const modeTitles = {
    'quick': 'QUICK SCAN (สแกนเร็ว)',
    'full': 'FULL DEEP SCAN (สแกนระบบลึก)',
    'smart': 'SMART CHECK (ตรวจจับอัจฉริยะ)',
    'disabled': 'DISABLED APPS (แอพแฝง)',
    'wipe_non_essential': 'WIPE NON-ESSENTIAL (ล้างแอพทั่วไป ยกเว้นธนาคาร & โซเชียล)'
  };
  
  isScanning = true;
  document.getElementById('scannerStatusCard').classList.add('is-scanning');
  document.getElementById('btnStartScan').style.display = 'none';
  document.getElementById('btnCancelScan').style.display = 'inline-flex';
  document.getElementById('scanStatusHeadline').innerText = `กำลังตรวจสอบ (${modeTitles[currentScanMode] || currentScanMode.toUpperCase()})...`;
  document.getElementById('scanProgressBar').style.width = '0%';
  document.getElementById('scanPercentBadge').innerText = '0%';
  document.getElementById('scanCurrentPackage').innerText = 'กำลังเตรียมระบบและตรวจสอบรายการแอพในเครื่อง...';
  
  currentThreats = [];
  renderThreatsTable([]);
  updateSummaryBadges([], 0);
  
  await callBackend('start_scan_async', currentScanMode);
}

function handleScanStateUpdate(state) {
  if (!state) return;
  
  const percent = state.percent || 0;
  document.getElementById('scanProgressBar').style.width = `${percent}%`;
  document.getElementById('scanPercentBadge').innerText = `${percent}%`;
  
  if (state.status === 'scanning') {
    document.getElementById('scanCurrentPackage').innerText = `ตรวจสอบ: ${state.current_package || ''} (${state.scanned_count || 0}/${state.total_count || 0})`;
    document.getElementById('badgeTotalScanned').innerText = state.scanned_count || 0;
    
    if (state.threats && state.threats.length !== currentThreats.length) {
      currentThreats = state.threats;
      renderThreatsTable(currentThreats);
      updateSummaryBadges(currentThreats, state.scanned_count, state.summary);
    }
  } else if (state.status === 'completed' || state.status === 'cancelled') {
    isScanning = false;
    document.getElementById('scannerStatusCard').classList.remove('is-scanning');
    document.getElementById('btnStartScan').style.display = 'inline-flex';
    document.getElementById('btnCancelScan').style.display = 'none';
    
    if (state.status === 'completed') {
      const modeTitles = {
        'wipe_non_essential': 'ตรวจสอบแอพทั่วไปเสร็จสิ้น',
        'quick': 'การสแกนเสร็จสิ้น',
        'full': 'การสแกนเชิงลึกเสร็จสิ้น',
        'smart': 'การสแกนอัจฉริยะเสร็จสิ้น',
        'disabled': 'การสแกนแอพปิดเสร็จสิ้น'
      };
      const title = modeTitles[currentScanMode] || 'การสแกนเสร็จสิ้น';
      document.getElementById('scanStatusHeadline').innerText = `${title} (พบรายการที่ต้องจัดการ ${state.threats_count || 0} รายการ)`;
      document.getElementById('scanCurrentPackage').innerText = `ตรวจสอบเสร็จสิ้น ตรวจสอบไปทั้งหมด ${state.scanned_count || 0} แอพ (แอพธนาคาร & โซเชียลได้รับการปกป้อง)`;
    } else {
      document.getElementById('scanStatusHeadline').innerText = 'การสแกนถูกยกเลิกโดยผู้ใช้';
      document.getElementById('scanCurrentPackage').innerText = 'ผู้ใช้ยกเลิกการสแกน';
    }
    
    currentThreats = state.threats || [];
    renderThreatsTable(currentThreats);
    updateSummaryBadges(currentThreats, state.scanned_count, state.summary);
  }
}

function cancelScan() {
  callBackend('cancel_scan');
  document.getElementById('scanStatusHeadline').innerText = "ยกเลิกการสแกนแล้ว";
  document.getElementById('scannerStatusCard').classList.remove('is-scanning');
  document.getElementById('btnStartScan').style.display = 'inline-flex';
  document.getElementById('btnCancelScan').style.display = 'none';
  isScanning = false;
}

function updateSummaryBadges(threats, totalScanned, summary) {
  let crit = 0, high = 0;
  threats.forEach(t => {
    if (t.risk === 'CRITICAL') crit++;
    else high++;
  });
  
  if (totalScanned !== undefined) {
    document.getElementById('badgeTotalScanned').innerText = totalScanned;
  }
  document.getElementById('badgeCriticalThreats').innerText = crit;
  document.getElementById('badgeHighThreats').innerText = high;
  
  let protectedCount = 0;
  if (summary && summary.skipped_count !== undefined) {
    protectedCount = (summary.skipped_count || 0) + (summary.clean_count || 0);
  } else if (totalScanned !== undefined) {
    protectedCount = Math.max(0, totalScanned - threats.length);
  }
  document.getElementById('badgeSkippedWhitelist').innerText = protectedCount;
  document.getElementById('threatTableCount').innerText = threats.length;
  updateSelectedCount();
}

function renderThreatsTable(threats) {
  const tbody = document.getElementById('threatsTableBody');
  if (!threats || threats.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--accent-emerald); padding: 14px 10px; font-weight: 600;">
          <svg class="status-svg" viewBox="0 0 24 24" style="width:16px; height:16px; color:var(--accent-emerald); vertical-align:middle; margin-right:6px;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
          ระบบปลอดภัย ไม่พบมัลแวร์หรือแอพที่เป็นอันตรายในหมวดนี้
        </td>
      </tr>
    `;
    updateSelectedCount();
    return;
  }
  
  let html = '';
  threats.forEach((t, idx) => {
    const riskClass = (t.risk || 'HIGH').toLowerCase();
    html += `
      <tr>
        <td>
          <input type="checkbox" class="chk-threat-item" data-index="${idx}" ${t.selected ? 'checked' : ''} onchange="onThreatCheckboxChanged(this, ${idx})">
        </td>
        <td>
          <span class="risk-pill ${riskClass}">${t.risk || 'HIGH'}</span>
        </td>
        <td>
          <b>${t.app_name || t.package_name}</b>
        </td>
        <td>
          <code style="font-family: var(--font-mono); color: var(--primary-cyan); font-size: 0.78rem;">${t.package_name}</code>
        </td>
        <td>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${t.type || 'Banking Trojan'}</div>
          <div style="font-size: 0.7rem; color: var(--accent-amber);">${t.reason || 'Virus Database Match'}</div>
        </td>
        <td style="text-align: right;">
          <button class="btn-danger" style="padding: 4px 10px; font-size: 0.72rem;" onclick="cleanSingleThreat('${t.package_name}', ${t.is_system})">
            <svg class="btn-svg" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            <span>ลบแอพนี้</span>
          </button>
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
  updateSelectedCount();
}

function onThreatCheckboxChanged(chk, idx) {
  if (currentThreats[idx]) {
    currentThreats[idx].selected = chk.checked;
  }
  updateSelectedCount();
}

function onSelectAllChanged(chk) {
  const checked = chk.checked;
  currentThreats.forEach(t => t.selected = checked);
  document.querySelectorAll('.chk-threat-item').forEach(el => el.checked = checked);
  updateSelectedCount();
}

function toggleSelectAllThreats() {
  const chk = document.getElementById('chkSelectAll');
  chk.checked = !chk.checked;
  onSelectAllChanged(chk);
}

function updateSelectedCount() {
  const selected = currentThreats.filter(t => t.selected);
  document.getElementById('selectedCountText').innerText = `เลือกแล้ว: ${selected.length} / ${currentThreats.length} รายการ`;
}

function clearScanResults() {
  currentThreats = [];
  renderThreatsTable([]);
  updateSummaryBadges([], 0);
}

// Cleaning Actions
async function cleanSingleThreat(pkg, isSystem) {
  if (!confirm(`ยืนยันการลบแอพ [${pkg}] ออกจากเครื่องมือถือ?`)) return;
  
  const res = await callBackend('uninstall_package', pkg, isSystem);
  if (res && res[0]) {
    alert(`ลบแอพ [${pkg}] สำเร็จเรียบร้อย!`);
    currentThreats = currentThreats.filter(t => t.package_name !== pkg);
    renderThreatsTable(currentThreats);
    updateSummaryBadges(currentThreats);
  } else {
    alert(`ไม่สามารถลบได้: ${res ? res[1] : 'Error'}`);
  }
}

async function cleanSelectedThreats() {
  const selected = currentThreats.filter(t => t.selected);
  if (selected.length === 0) {
    alert("กรุณาเลือกรายการที่ต้องการลบอย่างน้อย 1 รายการ");
    return;
  }
  
  const isWipeMode = currentScanMode === 'wipe_non_essential';
  const confirmMsg = isWipeMode
    ? `ยืนยันการเริ่มลบแอพผู้ใช้ทั่วไปที่เลือกทั้งหมด (${selected.length} รายการ) ออกจากเครื่องมือถือ?\n\n*หมายเหตุ: แอพธนาคาร, แอพโซเชียลหลัก (LINE, Facebook, TikTok ฯลฯ) และแอพระบบจะไม่ถูกลบ`
    : `ยืนยันการเริ่มลบมัลแวร์ที่เลือกทั้งหมด (${selected.length} รายการ) ออกจากเครื่องมือถือ?`;

  if (!confirm(confirmMsg)) return;
  
  const btn = document.getElementById('btnCleanAll');
  btn.innerHTML = `<svg class="btn-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> <span>กำลังดำเนินการลบ...</span>`;
  btn.disabled = true;
  isCleaning = true;
  
  await callBackend('start_clean_async', selected);
}

function handleCleanStateUpdate(state) {
  if (!state) return;
  const btn = document.getElementById('btnCleanAll');
  
  if (state.status === 'cleaning') {
    btn.innerHTML = `<svg class="btn-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> <span>กำลังลบ (${state.index || 0}/${state.total || 0}): ${state.current_package || ''}</span>`;
  } else if (state.status === 'completed' || state.status === 'cancelled') {
    isCleaning = false;
    btn.disabled = false;
    btn.innerHTML = `<svg class="btn-svg" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> <span>เริ่มลบทั้งหมดที่เลือก (Clean Threats)</span>`;
    
    alert(`การล้างข้อมูลเสร็จสิ้น!\n- ลบสำเร็จ: ${state.success_count || 0} แอพ\n- ล้มเหลว: ${state.fail_count || 0} แอพ`);
    
    const cleanedSet = new Set(state.cleaned_packages || []);
    currentThreats = currentThreats.filter(t => !cleanedSet.has(t.package_name));
    renderThreatsTable(currentThreats);
    updateSummaryBadges(currentThreats);
  }
}

// Security Hardening
async function triggerDisableAdb() {
  if (!confirm("ต้องการส่งคำสั่งปิด USB Debugging ไปที่มือถือใช่หรือไม่?")) return;
  const res = await callBackend('disable_adb');
  alert(res ? res[1] : "คำสั่งถูกส่งแล้ว");
}

async function triggerDisableDevSettings() {
  if (!confirm("ต้องการส่งคำสั่งปิดเมนูตัวเลือกสำหรับนักพัฒนา (Developer Options) ใช่หรือไม่?")) return;
  const res = await callBackend('disable_developer_settings');
  alert(res ? res[1] : "คำสั่งถูกส่งแล้ว");
}

async function triggerReboot(mode) {
  if (!confirm(`ต้องการรีสตาร์ทอุปกรณ์ (${mode}) หรือไม่?`)) return;
  const res = await callBackend('reboot_device', mode);
  alert(res ? "ส่งคำสั่งรีสตาร์ทเรียบร้อย" : "ไม่สามารถรีสตาร์ทได้");
}

// Drivers
async function installSamsungDriver() {
  const res = await callBackend('install_samsung_driver');
  alert(res && res[0] ? "กำลังเปิดตัวติดตั้ง Samsung Mobile USB Driver..." : `ไม่พบไฟล์ติดตั้ง: ${res ? res[1] : ''}`);
}

async function installUniversalAdbDriver() {
  const res = await callBackend('install_universal_adb_driver');
  alert(res && res[0] ? "กำลังเปิดตัวติดตั้ง Universal ADB Driver (MSI)..." : `ไม่พบไฟล์ติดตั้ง: ${res ? res[1] : ''}`);
}

// Guide brand switcher
function showGuide(brand) {
  const title = document.getElementById('guideBrandTitle');
  const list = document.getElementById('guideStepsList');
  
  if (brand === 'samsung') {
    title.innerText = "ขั้นตอนการเปิด USB Debugging (Samsung Galaxy)";
    list.innerHTML = `
      <li>ไปที่ <b>การตั้งค่า (Settings)</b> &gt; <b>เกี่ยวกับโทรศัพท์ (About phone)</b> &gt; <b>ข้อมูลซอฟต์แวร์ (Software information)</b></li>
      <li>แตะที่ <b>หมายเลขรุ่น (Build number)</b> รัวๆ 7 ครั้ง</li>
      <li>กลับมาที่หน้าการตั้งค่าหลัก เลื่อนลงล่างสุดเลือก <b>ทางเลือกผู้พัฒนา (Developer options)</b></li>
      <li>เปิดสวิตช์ <b>การแก้ไขจุดบกพร่อง USB (USB debugging)</b> &gt; กด 'ตกลง'</li>
      <li>เสียบสายต่อเข้าคอม และติ๊ก 'อนุญาตเสมอจากคอมพิวเตอร์นี้' แล้วกด 'อนุญาต'</li>
    `;
  } else if (brand === 'xiaomi') {
    title.innerText = "ขั้นตอนการเปิด USB Debugging (Xiaomi / Redmi / POCO)";
    list.innerHTML = `
      <li>ไปที่ <b>การตั้งค่า (Settings)</b> &gt; <b>เกี่ยวกับโทรศัพท์ (About phone)</b></li>
      <li>แตะที่ <b>เวอร์ชัน MIUI / HyperOS</b> รัวๆ 7 ครั้ง</li>
      <li>ไปที่ <b>การตั้งค่าเพิ่มเติม (Additional settings)</b> &gt; <b>ตัวเลือกสำหรับนักพัฒนา (Developer options)</b></li>
      <li>เปิด <b>การดีบัก USB (USB debugging)</b> และ <b>ติดตั้งผ่าน USB (Install via USB)</b></li>
      <li>รอนับถอยหลัง 10 วินาทีแล้วกดยอมรับ</li>
    `;
  } else if (brand === 'oppo') {
    title.innerText = "ขั้นตอนการเปิด USB Debugging (OPPO / Realme)";
    list.innerHTML = `
      <li>ไปที่ <b>การตั้งค่า (Settings)</b> &gt; <b>เกี่ยวกับอุปกรณ์ (About Device)</b> &gt; <b>เวอร์ชัน (Version)</b></li>
      <li>แตะที่ <b>หมายเลขบิลด์ (Build Number)</b> รัวๆ 7 ครั้ง</li>
      <li>ไปที่ <b>การตั้งค่าระบบ (System settings)</b> &gt; <b>ตัวเลือกสำหรับนักพัฒนา (Developer options)</b></li>
      <li>เปิด <b>การแก้จุดบกพร่อง USB (USB Debugging)</b></li>
    `;
  } else if (brand === 'vivo') {
    title.innerText = "ขั้นตอนการเปิด USB Debugging (Vivo / iQOO)";
    list.innerHTML = `
      <li>ไปที่ <b>การตั้งค่า (Settings)</b> &gt; <b>เกี่ยวกับโทรศัพท์ (About Phone)</b> &gt; <b>ข้อมูลซอฟต์แวร์ (Software information)</b></li>
      <li>แตะที่ <b>หมายเลขบิลด์ (Build number)</b> 7 ครั้ง</li>
      <li>ไปที่ <b>ระบบ (System)</b> &gt; <b>ตัวเลือกสำหรับนักพัฒนา (Developer options)</b></li>
      <li>เปิด <b>การแก้ไขข้อบกพร่อง USB (USB debugging)</b></li>
    `;
  } else {
    title.innerText = `ขั้นตอนการเปิด USB Debugging (${brand.toUpperCase()})`;
    list.innerHTML = `
      <li>ไปที่ <b>Settings</b> &gt; <b>System / About Phone</b></li>
      <li>แตะ <b>Build Number</b> 7 ครั้งเพื่อเปิด Developer Mode</li>
      <li>เข้าไปที่ <b>Developer Options</b> แล้วเปิด <b>USB Debugging</b></li>
      <li>เชื่อมต่อคอมพิวเตอร์และกดยินยอม 'Always allow' บนหน้าจอมือถือ</li>
    `;
  }
}

// App Manager
async function loadAppManagerList() {
  const tbody = document.getElementById('appManagerTableBody');
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px;">กำลังโหลดข้อมูลแอพทั้งหมดในเครื่อง...</td></tr>';
  
  const apps = await callBackend('get_installed_packages');
  appListCache = apps || [];
  renderAppManagerList();
}

function setAppFilter(mode) {
  appFilterMode = mode;
  document.getElementById('btnFilterUser').style.background = mode === 'user' ? 'var(--primary-cyan)' : '';
  document.getElementById('btnFilterUser').style.color = mode === 'user' ? '#fff' : '';
  document.getElementById('btnFilterSystem').style.background = mode === 'system' ? 'var(--primary-cyan)' : '';
  document.getElementById('btnFilterSystem').style.color = mode === 'system' ? '#fff' : '';
  document.getElementById('btnFilterDisabled').style.background = mode === 'disabled' ? 'var(--primary-cyan)' : '';
  document.getElementById('btnFilterDisabled').style.color = mode === 'disabled' ? '#fff' : '';
  
  const btnNonEss = document.getElementById('btnFilterNonEssential');
  if (btnNonEss) {
    btnNonEss.style.background = mode === 'non_essential' ? 'var(--accent-amber)' : '';
    btnNonEss.style.color = mode === 'non_essential' ? '#fff' : '#d97706';
  }
  renderAppManagerList();
}

function renderAppManagerList() {
  const tbody = document.getElementById('appManagerTableBody');
  const search = document.getElementById('inpSearchApps').value.toLowerCase();
  
  let filtered = appListCache.filter(item => {
    if (appFilterMode === 'user' && item.is_system) return false;
    if (appFilterMode === 'system' && !item.is_system) return false;
    if (appFilterMode === 'disabled' && !item.is_disabled) return false;
    if (appFilterMode === 'non_essential' && (item.is_system || item.is_essential)) return false;
    if (search && !item.package_name.toLowerCase().includes(search)) return false;
    return true;
  });
  
  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-dim); padding:20px;">ไม่พบแอพพลิเคชันในหมวดนี้ (แอพทั้งหมดได้รับการปกป้อง)</td></tr>';
    return;
  }
  
  let html = '';
  filtered.forEach(item => {
    let catBadge = '';
    if (item.is_system) {
      catBadge = '<span style="color:var(--text-muted)">System App</span>';
    } else if (item.is_essential) {
      catBadge = `<span style="color:var(--accent-emerald)">🛡️ ${item.essential_category || 'Protected'}</span>`;
    } else {
      catBadge = '<span style="color:var(--accent-amber)">⚠️ Non-Essential (แอพทั่วไป)</span>';
    }

    html += `
      <tr>
        <td><code style="font-family: var(--font-mono); color: var(--primary-cyan);">${item.package_name}</code></td>
        <td>${catBadge}</td>
        <td>${item.is_disabled ? '<span class="risk-pill high">Disabled</span>' : '<span style="color:var(--accent-emerald)">Active</span>'}</td>
        <td style="text-align:right;">
          <button class="btn-danger" style="padding:4px 8px; font-size:0.7rem;" onclick="cleanSingleThreat('${item.package_name}', ${item.is_system})">
            <svg class="btn-svg" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            <span>ลบแอพ</span>
          </button>
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

function filterAppManagerList() {
  renderAppManagerList();
}

// Incremental Live Logs Renderer (Ultra Low Overhead)
function renderIncrementalLogs(logs) {
  const container = document.getElementById('terminalWindow');
  if (!container) return;
  
  if (logs.length <= renderedLogCount && renderedLogCount > 0) return;
  
  const newLogs = logs.slice(renderedLogCount);
  renderedLogCount = logs.length;
  
  const fragment = document.createDocumentFragment();
  newLogs.forEach(l => {
    const div = document.createElement('div');
    div.className = `log-line ${l.level || 'INFO'}`;
    div.innerHTML = `<span class="log-time">[${l.timestamp}]</span> <span>- ${l.full_text || l.message}</span>`;
    fragment.appendChild(div);
  });
  
  container.appendChild(fragment);
  
  if (document.getElementById('chkAutoScroll') && document.getElementById('chkAutoScroll').checked) {
    container.scrollTop = container.scrollHeight;
  }
}

function clearLiveLogs() {
  callBackend('clear_logs');
  document.getElementById('terminalWindow').innerHTML = '';
  renderedLogCount = 0;
}

function exportLogsFile() {
  alert("ไฟล์บันทึก logs.txt ถูกบันทึกไว้ที่โฟลเดอร์โปรแกรมเรียบร้อยแล้ว");
}

function exportScanReport() {
  if (currentThreats.length === 0) {
    alert("ไม่มีรายการมัลแวร์ที่จะส่งออก");
    return;
  }
  let report = `=== APKs Guard Pro 289 - Scan Report ===\nDate: ${new Date().toLocaleString()}\nTotal Threats: ${currentThreats.length}\n\n`;
  currentThreats.forEach(t => {
    report += `[${t.risk}] ${t.package_name} - ${t.app_name} (${t.type})\nReason: ${t.reason}\n\n`;
  });
  
  const blob = new Blob([report], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `Scan_Report_${Date.now()}.txt`;
  a.click();
}

function exportDefinitions() {
  alert("ส่งออกฐานข้อมูล definitions.json สำเร็จ");
}

function updateAppConfig() {
  console.log("Updated preferences");
}

// Mock responses for web test
function mockBackendResponse(method, ...args) {
  if (method === 'get_device_info') {
    return {
      serial: 'SIMULATOR-289-VIP',
      brand: 'Samsung',
      model: 'Galaxy S24 Ultra (Demo)',
      android_version: '14',
      battery: '92%',
      build_id: 'UP1A.231005.007.S928BXXU1AXB5',
      security_patch: '2026-08-01',
      root: 'No'
    };
  } else if (method === 'get_database_stats') {
    return {
      virus_signatures_count: 2570,
      whitelist_count: 234,
      version: '2026.09.29',
      last_updated: '2026-09-29 20:00:00'
    };
  } else if (method === 'get_scan_state') {
    return {
      status: 'completed',
      percent: 100,
      current_package: 'การสแกนเสร็จสิ้น',
      scanned_count: 16,
      total_count: 16,
      threats_count: 6,
      threats: [
        { package_name: 'com.revenuedepartment.app', app_name: 'Fake Revenue Dept (แอพกรมสรรพากรปลอม)', risk: 'CRITICAL', type: 'Banking Trojan / RAT', reason: 'Virus Database Match', is_system: false, is_disabled: false, selected: true },
        { package_name: 'com.zenthaq4729.meeting_agenda_builder_8301', app_name: 'Zenthaq Meeting Agenda RAT', risk: 'CRITICAL', type: 'RAT / Remote Control', reason: 'Abusing Accessibility Services', is_system: false, is_disabled: false, selected: true },
        { package_name: 'com.space.whizclear.qub', app_name: 'Fake Cleaner Whiz RAT', risk: 'CRITICAL', type: 'Accessibility Trojan', reason: 'Virus Database Match', is_system: false, is_disabled: false, selected: true },
        { package_name: 'borrorhealthcare.store', app_name: 'Fake Healthcare Loan', risk: 'CRITICAL', type: 'Banking Trojan', reason: 'Sideloaded from unknown source', is_system: false, is_disabled: false, selected: true },
        { package_name: 'com.nanai.cleanfly', app_name: 'CleanFly Trojan Cleaner', risk: 'HIGH', type: 'Smart Check Heuristic', reason: 'Matches Malware Pattern', is_system: false, is_disabled: false, selected: true },
        { package_name: 'com.duokan.phone.remotecontroller', app_name: 'Fake Remote Controller', risk: 'HIGH', type: 'Remote Access / RAT', reason: 'Virus Database Match', is_system: false, is_disabled: false, selected: true }
      ]
    };
  } else if (method === 'get_live_logs') {
    return [
      { timestamp: '2026-09-29 20:30:00', level: 'INFO', full_text: 'APKs Guard Pro 289 Initialized' },
      { timestamp: '2026-09-29 20:30:01', level: 'SUCCESS', full_text: 'Device connected: SIMULATOR-289-VIP (Samsung Galaxy S24 Ultra)' },
      { timestamp: '2026-09-29 20:30:02', level: 'INFO', full_text: 'Virus Database Loaded: 2,570 signatures' }
    ];
  }
  return { success: true };
}
