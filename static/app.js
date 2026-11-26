/* ═══════════════════════════════════════════
   PixelVeil — Frontend Logic
   ═══════════════════════════════════════════ */

// ─── State ───────────────────────────────────
let sessionId = null;
let originalMeta = null;
let currentMeta = null;
let stagedChanges = {}; // { field: { old, new } }
let currentOutputFile = null;
let editingField = null;
let editingGroup = null;
let cameraList = [];
let lastAgentCascade = {};
let checkCompatDebounce = null;

const API = '';

// ─── Init ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupUploadZone();
});

// ─── Upload Zone ──────────────────────────────
function setupUploadZone() {
  const zone = document.getElementById('upload-zone');
  const input = document.getElementById('file-input');

  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault(); zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  });
  zone.addEventListener('click', (e) => {
    if (e.target.tagName !== 'BUTTON') input.click();
  });
  input.addEventListener('change', () => {
    if (input.files[0]) handleFileUpload(input.files[0]);
  });
}

async function handleFileUpload(file) {
  if (!file.name.match(/\.(jpg|jpeg)$/i)) {
    showToast('Only JPEG/JPG files are supported.', 'error'); return;
  }

  // Show progress
  document.getElementById('upload-progress').style.display = 'block';
  animateProgress();

  const form = new FormData();
  form.append('image', file);

  try {
    const res = await fetch(`${API}/api/upload`, { method: 'POST', body: form });
    const data = await res.json();

    if (data.error) { showToast(data.error, 'error'); return; }

    sessionId = data.session_id;
    originalMeta = data.metadata;
    currentMeta = data.metadata;
    cameraList = data.camera_db || [];
    stagedChanges = {};
    currentOutputFile = null;

    // Show image preview
    const reader = new FileReader();
    reader.onload = (e) => {
      document.getElementById('image-preview-mini').innerHTML =
        `<img src="${e.target.result}" alt="Preview" />`;
    };
    reader.readAsDataURL(file);

    // Populate camera selects
    populateCameraSelects();

    // Render metadata
    renderMetadata(currentMeta);
    updateStagedChanges();

    // Switch to editor
    document.getElementById('upload-section').style.display = 'none';
    document.getElementById('editor-section').style.display = 'block';

    showToast('Metadata extracted successfully!', 'success');
  } catch (err) {
    showToast('Upload failed: ' + err.message, 'error');
  } finally {
    document.getElementById('upload-progress').style.display = 'none';
  }
}

function animateProgress() {
  const fill = document.getElementById('progress-fill');
  const labels = ['Reading file...', 'Parsing EXIF...', 'Extracting GPS...', 'Reading XMP...', 'Finalizing...'];
  let w = 0, li = 0;
  const interval = setInterval(() => {
    w = Math.min(w + Math.random() * 18, 95);
    fill.style.width = w + '%';
    if (li < labels.length) {
      document.getElementById('progress-label').textContent = labels[li++];
    }
    if (w >= 95) clearInterval(interval);
  }, 300);
}

// ─── Render Metadata ──────────────────────────
const GROUP_COLORS = {
  'EXIF': 'exif-color', 'GPS': 'gps-color', 'Image': 'image-color',
  'File': 'file-color', 'Thumbnail': 'thumb-color', 'Computed': 'computed-color',
  'XMP': 'exif-color', 'Interop': 'computed-color'
};

const EDITABLE_FIELDS = new Set([
  'Make','Model','Software','DateTime','DateTimeOriginal','DateTimeDigitized',
  'Artist','Copyright','Orientation','XResolution','YResolution',
  'ExposureTime','FNumber','ISOSpeedRatings','FocalLength','Flash',
  'WhiteBalance','ExposureMode','MeteringMode','ExposureProgram','ColorSpace',
  'PixelXDimension','PixelYDimension','LensMake','LensModel','SceneCaptureType',
  'UserComment','MakerNote'
]);

function renderMetadata(meta) {
  const container = document.getElementById('metadata-container');
  container.innerHTML = '';

  for (const [group, fields] of Object.entries(meta)) {
    if (!fields || typeof fields !== 'object') continue;
    const entries = Object.entries(fields);
    if (entries.length === 0) continue;

    const colorClass = GROUP_COLORS[group] || 'computed-color';
    const groupEl = document.createElement('div');
    groupEl.className = 'meta-group';
    groupEl.dataset.group = group;

    groupEl.innerHTML = `
      <div class="meta-group-header" onclick="toggleGroup('${group}')">
        <span class="meta-group-title ${colorClass}">${group}</span>
        <span class="meta-group-count">${entries.length} fields</span>
        <span class="meta-group-chevron open" id="chevron-${group}">▶</span>
      </div>
      <div class="meta-group-body open" id="body-${group}"></div>
    `;

    const body = groupEl.querySelector('.meta-group-body');

    for (const [field, value] of entries) {
      const isBinary = typeof value === 'string' && value.includes('<binary');
      const isMakerNote = field === 'MakerNote';
      const isEditable = EDITABLE_FIELDS.has(field) && !isBinary;
      const isModified = stagedChanges[field] !== undefined;

      const row = document.createElement('div');
      row.className = `meta-row${isModified ? ' modified' : ''}`;
      row.dataset.field = field;
      row.dataset.group = group;

      const displayVal = formatValue(value);
      const valClass = isBinary ? 'binary' : '';

      row.innerHTML = `
        <span class="meta-field">${field}</span>
        <span class="meta-value ${valClass}" id="val-${group}-${field}">${displayVal}</span>
        ${isEditable ? `<button class="meta-edit-btn" onclick="openEditModal('${group}','${field}',event)">Edit</button>` : '<span></span>'}
      `;
      body.appendChild(row);
    }

    container.appendChild(groupEl);
  }
}

function formatValue(val) {
  if (val === null || val === undefined) return '<span style="color:var(--text-muted)">—</span>';
  if (typeof val === 'boolean') return val ? '✓ Yes' : '✗ No';
  if (typeof val === 'object') return JSON.stringify(val).substring(0, 120);
  const s = String(val);
  if (s.length > 150) return s.substring(0, 147) + '...';
  return escapeHtml(s);
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function toggleGroup(group) {
  const body = document.getElementById(`body-${group}`);
  const chevron = document.getElementById(`chevron-${group}`);
  if (!body) return;
  body.classList.toggle('open');
  chevron.classList.toggle('open');
}

let allExpanded = false;
function toggleAllGroups() {
  allExpanded = !allExpanded;
  document.querySelectorAll('.meta-group-body').forEach(b => {
    b.classList.toggle('open', allExpanded);
  });
  document.querySelectorAll('.meta-group-chevron').forEach(c => {
    c.classList.toggle('open', allExpanded);
  });
  document.getElementById('expand-all-btn').textContent = allExpanded ? 'Collapse All' : 'Expand All';
}

function filterMetadata(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('.meta-row').forEach(row => {
    const field = row.dataset.field.toLowerCase();
    const val = row.querySelector('.meta-value')?.textContent.toLowerCase() || '';
    row.style.display = (!q || field.includes(q) || val.includes(q)) ? '' : 'none';
  });
}

function populateCameraSelects() {
  const sel = document.getElementById('edit-camera-select');
  sel.innerHTML = '<option value="">-- Choose camera from database --</option>';
  cameraList.forEach(cam => {
    const opt = document.createElement('option');
    opt.value = cam; opt.textContent = cam;
    sel.appendChild(opt);
  });
}

// ─── Edit Modal ───────────────────────────────
function openEditModal(group, field, event) {
  event?.stopPropagation();
  editingField = field;
  editingGroup = group;

  const currentVal = getFieldValue(group, field);
  document.getElementById('edit-modal-title').textContent = `Edit: ${field}`;
  document.getElementById('edit-field-info').textContent = `Group: ${group}`;
  document.getElementById('edit-current-val').textContent = currentVal ?? '—';
  document.getElementById('edit-new-val').value = stagedChanges[field]?.new ?? (typeof currentVal === 'string' ? currentVal : '');
  document.getElementById('compat-preview').style.display = 'none';
  document.getElementById('compat-issues-preview').innerHTML = '';

  // Show camera selector for Make/Model fields
  const isModelField = field === 'Model' || field === 'Make';
  document.getElementById('edit-camera-select-wrap').style.display = isModelField ? 'block' : 'none';

  // Reset cascade preview button — only shown after a camera is picked
  const prevBtn = document.getElementById('preview-cascade-btn');
  if (prevBtn) prevBtn.style.display = 'none';
  // Reset the select dropdown
  const sel = document.getElementById('edit-camera-select');
  if (sel) sel.value = '';

  document.getElementById('edit-modal').style.display = 'flex';
  document.getElementById('edit-new-val').focus();

  // Live compat check on input
  document.getElementById('edit-new-val').oninput = () => {
    clearTimeout(checkCompatDebounce);
    checkCompatDebounce = setTimeout(checkCompatibility, 600);
  };
}

function getFieldValue(group, field) {
  if (currentMeta?.[group]?.[field] !== undefined) return currentMeta[group][field];
  for (const g of Object.values(currentMeta || {})) {
    if (g && typeof g === 'object' && g[field] !== undefined) return g[field];
  }
  return null;
}

function closeEditModal(event) {
  if (event.target.id === 'edit-modal') closeEditModalBtn();
}
function closeEditModalBtn() {
  document.getElementById('edit-modal').style.display = 'none';
  editingField = null; editingGroup = null;
}

async function onCameraSelect(cameraName) {
  if (!cameraName) return;

  // Set the text input to the full camera name so compat check works
  document.getElementById('edit-new-val').value = cameraName;
  checkCompatibility();

  // Show the cascade preview button
  const prevBtn = document.getElementById('preview-cascade-btn');
  if (prevBtn) prevBtn.style.display = 'inline-flex';

  // Auto-fetch the full cascade for this camera and store it
  if (!sessionId) return;
  try {
    const res = await fetch(`${API}/api/get-cascade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_camera: cameraName })
    });
    const data = await res.json();
    lastAgentCascade = data.cascade_changes || {};
    const count = Object.keys(lastAgentCascade).filter(k => !k.startsWith('_')).length;
    showToast(`${cameraName} selected — ${count} fields will cascade. Click "Preview Cascade".`, 'info');
  } catch (e) {
    console.warn('Could not fetch cascade for', cameraName, e);
  }
}

async function checkCompatibility() {
  const newVal = document.getElementById('edit-new-val').value.trim();
  if (!newVal || !sessionId || !editingField) return;

  const proposed = { [editingField]: newVal };

  try {
    const res = await fetch(`${API}/api/check-compatibility`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, proposed_changes: proposed })
    });
    const data = await res.json();

    // Show compat preview
    const score = data.compatibility_score;
    const scoreColor = score >= 75 ? 'var(--green)' : score >= 50 ? 'var(--orange)' : 'var(--red)';
    const barColor = score >= 75 ? 'var(--green)' : score >= 50 ? 'var(--orange)' : 'var(--red)';

    document.getElementById('compat-preview').style.display = 'block';
    document.getElementById('compat-score-val').textContent = score + '%';
    document.getElementById('compat-score-val').style.color = scoreColor;
    document.getElementById('compat-bar').style.width = score + '%';
    document.getElementById('compat-bar').style.background = barColor;

    const issuesEl = document.getElementById('compat-issues-preview');
    issuesEl.innerHTML = '';
    if (data.issues?.length) {
      data.issues.slice(0, 3).forEach(issue => {
        const div = document.createElement('div');
        div.className = `issue-item issue-${issue.severity}`;
        div.innerHTML = `<span class="issue-sev">${issue.severity}</span> <span>${issue.issue}</span>`;
        issuesEl.appendChild(div);
      });
    }
  } catch (err) {
    console.warn('Compat check failed:', err);
  }
}

function stageFieldChange() {
  const newVal = document.getElementById('edit-new-val').value.trim();
  if (!newVal || !editingField) { showToast('Enter a value first.', 'error'); return; }

  const oldVal = getFieldValue(editingGroup, editingField);
  stagedChanges[editingField] = { old: oldVal, new: newVal, group: editingGroup };

  updateStagedChanges();
  markRowModified(editingGroup, editingField, newVal);
  closeEditModalBtn();
  showToast(`"${editingField}" staged for change.`, 'success');

  // Auto-show diff and download buttons
  document.getElementById('diff-btn').style.display = 'inline-flex';
}

async function runAgentForField() {
  const newVal = document.getElementById('edit-new-val').value.trim();
  if (!newVal || !editingField || !sessionId) { showToast('Enter a value and ensure image is uploaded.', 'error'); return; }

  closeEditModalBtn();

  // Show agent card
  const agentCard = document.getElementById('agent-card');
  agentCard.style.display = 'block';
  document.getElementById('agent-thinking').style.display = 'flex';
  document.getElementById('agent-score-bar').innerHTML = '';
  document.getElementById('agent-issues').innerHTML = '';
  document.getElementById('agent-analysis').innerHTML = '';
  document.getElementById('agent-risks').innerHTML = '';
  document.getElementById('agent-alternatives').innerHTML = '';
  document.getElementById('agent-cascade').innerHTML = '';
  document.getElementById('agent-recommendation').innerHTML = '';

  const oldVal = getFieldValue(editingGroup, editingField);

  try {
    const res = await fetch(`${API}/api/agent-suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        field_changed: editingField,
        old_value: oldVal,
        new_value: newVal
      })
    });
    const data = await res.json();
    document.getElementById('agent-thinking').style.display = 'none';
    renderAgentResult(data, editingField, newVal);
  } catch (err) {
    document.getElementById('agent-thinking').style.display = 'none';
    document.getElementById('agent-analysis').innerHTML = `<div style="color:var(--red);padding:12px 16px;font-size:0.85rem;">Agent error: ${err.message}</div>`;
  }
}

function renderAgentResult(data, field, newVal) {
  const { agent_result, compatibility_score, issues, cascade_changes } = data;
  lastAgentCascade = cascade_changes || {};

  // Score bar
  const score = compatibility_score;
  const scoreClass = score >= 75 ? 'score-high' : score >= 50 ? 'score-medium' : 'score-low';
  const barClass = score >= 75 ? 'score-bar-high' : score >= 50 ? 'score-bar-medium' : 'score-bar-low';
  const riskLevel = score >= 75 ? 'low' : score >= 50 ? 'medium' : 'high';

  document.getElementById('agent-score-bar').innerHTML = `
    <div class="score-row">
      <span class="score-label">Compatibility Score</span>
      <span class="score-value ${scoreClass}">${score}%</span>
    </div>
    <div class="score-bar-wrap"><div class="score-bar ${barClass}" style="width:${score}%"></div></div>
    <span class="risk-pill risk-${riskLevel}">Risk: ${riskLevel}</span>
  `;

  // Issues
  if (issues?.length) {
    const issuesEl = document.getElementById('agent-issues');
    issuesEl.innerHTML = issues.map(i => `
      <div class="issue-item issue-${i.severity}">
        <span class="issue-sev">${i.severity}</span>
        <span><span class="issue-field">${i.field}</span>: ${escapeHtml(i.issue)}</span>
      </div>
    `).join('');
  }

  // Agent analysis
  if (agent_result?.analysis) {
    document.getElementById('agent-analysis').textContent = agent_result.analysis;
  } else if (agent_result?.error) {
    document.getElementById('agent-analysis').innerHTML = `<span style="color:var(--red)">AI Agent: ${agent_result.error}</span>`;
  }

  // Forensic risks
  if (agent_result?.forensic_risks?.length) {
    document.getElementById('agent-risks').innerHTML = `
      <div class="risks-title">⚠ Forensic Risks</div>
      ${agent_result.forensic_risks.map(r => `<div class="risk-item">${escapeHtml(r)}</div>`).join('')}
    `;
  }

  // Alternatives
  const alts = agent_result?.alternatives;
  if (alts?.length) {
    document.getElementById('agent-alternatives').innerHTML = `
      <div class="alt-title">💡 AI Suggests These Instead</div>
      ${alts.map(a => `
        <div class="alt-item" onclick="quickSwapCamera('${escapeHtml(a.camera)}','${escapeHtml(field)}')">
          <span class="alt-score">${a.score}%</span>
          <div style="flex:1">
            <div class="alt-name">${escapeHtml(a.camera)}</div>
            <div class="alt-reason">${escapeHtml(a.reason)}</div>
          </div>
          <button class="alt-apply-btn">Use This</button>
        </div>
      `).join('')}
    `;
  }

  // Cascade
  const hasCascade = cascade_changes && Object.keys(cascade_changes).filter(k => !k.startsWith('_')).length > 0;
  if (hasCascade) {
    const fields = Object.entries(cascade_changes).filter(([k]) => !k.startsWith('_'));
    document.getElementById('agent-cascade').innerHTML = `
      <div class="cascade-title">🔄 Cascaded Changes (${fields.length} fields)</div>
      <button class="cascade-btn" onclick="showCascadeModal()">
        Preview & Apply Auto-Harmonize (${fields.length} fields)
      </button>
    `;
  }

  // Recommendation — normalize to lowercase, guard against null
  const rawRec = agent_result?.recommendation;
  if (rawRec) {
    // Normalize: "CHANGE_MODEL", "change model", "change_model" → "change_model"
    const rec = String(rawRec).toLowerCase().trim().replace(/[\s\-]+/g, '_');
    const isAbort   = rec.includes('abort');
    const isProceed = rec.includes('proceed');
    const recClass  = isProceed ? 'rec-proceed' : isAbort ? 'rec-abort' : 'rec-change';
    const recEmoji  = isProceed ? '✅' : isAbort ? '🛑' : '⚠️';
    const recLabel  = rec.replace(/_/g, ' ').toUpperCase();
    document.getElementById('agent-recommendation').innerHTML = `
      <div class="${recClass}">
        <div class="rec-label">${recEmoji} ${recLabel}</div>
        <div class="rec-text">${escapeHtml(agent_result.recommendation_reason || '')}</div>
      </div>
    `;
  }

  // Also stage the change
  const oldVal = getFieldValue(editingGroup || '', field);
  stagedChanges[field] = { old: oldVal, new: newVal, group: editingGroup || 'Image' };
  updateStagedChanges();
  markRowModified(editingGroup || 'Image', field, newVal);
  document.getElementById('diff-btn').style.display = 'inline-flex';
}

function quickSwapCamera(cameraName, field) {
  stagedChanges[field] = { old: getFieldValue('Image', field), new: cameraName, group: 'Image' };
  updateStagedChanges();
  showToast(`Switched to ${cameraName}`, 'info');
  // Also get cascade for this camera
  fetch(`${API}/api/get-cascade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_camera: cameraName })
  }).then(r => r.json()).then(d => {
    lastAgentCascade = d.cascade_changes || {};
  });
}

// ─── Staged Changes ───────────────────────────
function updateStagedChanges() {
  const list = document.getElementById('staged-changes-list');
  const count = Object.keys(stagedChanges).length;
  document.getElementById('changes-count').textContent = count;

  const applyBtn = document.getElementById('apply-btn');
  applyBtn.disabled = count === 0;

  if (count === 0) {
    list.innerHTML = '<p class="empty-hint">No changes staged yet. Edit a metadata field to begin.</p>';
    return;
  }

  list.innerHTML = Object.entries(stagedChanges).map(([field, {old: oldV, new: newV}]) => `
    <div class="staged-item">
      <span class="staged-field">${field}</span>
      <span class="staged-arrow">→</span>
      <span class="staged-val">${escapeHtml(String(newV))}</span>
      <span class="staged-remove" onclick="removeStagedChange('${field}')">✕</span>
    </div>
  `).join('');
}

function removeStagedChange(field) {
  delete stagedChanges[field];
  updateStagedChanges();
  // Remove modified styling
  document.querySelectorAll(`.meta-row[data-field="${field}"]`).forEach(r => r.classList.remove('modified'));
}

function clearChanges() {
  stagedChanges = {};
  updateStagedChanges();
  document.querySelectorAll('.meta-row.modified').forEach(r => r.classList.remove('modified'));
  showToast('All staged changes cleared.', 'info');
}

function markRowModified(group, field, newVal) {
  document.querySelectorAll(`.meta-row[data-field="${field}"]`).forEach(row => {
    row.classList.add('modified');
    const valEl = row.querySelector('.meta-value');
    if (valEl) valEl.textContent = newVal;
  });
}

// ─── Apply Changes ─────────────────────────────
async function applyChanges() {
  if (!sessionId || Object.keys(stagedChanges).length === 0) return;

  const applyBtn = document.getElementById('apply-btn');
  applyBtn.disabled = true;
  applyBtn.textContent = 'Applying...';

  const changes = {};
  for (const [field, {new: newVal}] of Object.entries(stagedChanges)) {
    changes[field] = newVal;
  }

  // GPS and MakerNote flags come from cascade (set when camera is selected or AI runs)
  const removeGps      = !!lastAgentCascade._remove_gps;
  const removeMakerNote = !!lastAgentCascade._remove_makernote || !!lastAgentCascade._makernote_warning;

  try {
    const res = await fetch(`${API}/api/apply-changes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        changes,
        remove_gps: removeGps,
        remove_makernote: removeMakerNote
      })
    });
    const data = await res.json();

    if (data.success) {
      currentMeta = data.metadata;
      currentOutputFile = data.output_file;
      stagedChanges = {};
      updateStagedChanges();
      renderMetadata(currentMeta);

      document.getElementById('download-btn').style.display = 'inline-flex';
      document.getElementById('diff-card').style.display = 'block';
      showToast('Changes applied to image!', 'success');
      runForensicDiff();
    } else {
      showToast('Failed to apply changes.', 'error');
    }
  } catch (err) {
    showToast('Apply error: ' + err.message, 'error');
  } finally {
    applyBtn.disabled = false;
    applyBtn.textContent = 'Apply Changes to Image';
  }
}

// ─── Cascade Modal ─────────────────────────────
function showCascadeModal() {
  if (!lastAgentCascade || Object.keys(lastAgentCascade).length === 0) {
    showToast('No cascade changes available. Run AI Agent first.', 'info'); return;
  }

  const listEl = document.getElementById('cascade-preview-list');
  const warningsEl = document.getElementById('cascade-warnings');
  listEl.innerHTML = '';
  warningsEl.innerHTML = '';

  const warnings = [];

  for (const [key, val] of Object.entries(lastAgentCascade)) {
    if (key.startsWith('_')) {
      if (key.endsWith('_note') || key.endsWith('_warning')) {
        warnings.push(val);
      } else if (key === '_remove_gps') {
        listEl.innerHTML += `
          <div class="cascade-item">
            <span class="cascade-field">GPS Data</span>
            <span class="cascade-action">→ REMOVE all GPS coordinates</span>
          </div>`;
      } else if (key === '_remove_makernote') {
        listEl.innerHTML += `
          <div class="cascade-item">
            <span class="cascade-field">MakerNote</span>
            <span class="cascade-action">→ STRIP MakerNote binary data</span>
          </div>`;
      }
      continue;
    }
    listEl.innerHTML += `
      <div class="cascade-item">
        <span class="cascade-field">${key}</span>
        <span class="cascade-action">→ "${escapeHtml(String(val))}"</span>
      </div>`;
  }

  warnings.forEach(w => {
    warningsEl.innerHTML += `<div class="warning-item">⚠ ${escapeHtml(w)}</div>`;
  });

  document.getElementById('cascade-modal').style.display = 'flex';
}

function closeCascadeModal(event) {
  if (event.target.id === 'cascade-modal') closeCascadeModalBtn();
}
function closeCascadeModalBtn() {
  document.getElementById('cascade-modal').style.display = 'none';
}

function applyCascadeChanges() {
  const userFields = Object.entries(lastAgentCascade).filter(([k]) => !k.startsWith('_'));
  if (userFields.length === 0) {
    showToast('No cascade fields to apply.', 'error'); return;
  }
  for (const [key, val] of userFields) {
    // Determine which group this field belongs to
    const exifFields = new Set([
      'ExposureTime','FNumber','ExposureProgram','ISOSpeedRatings','ExifVersion',
      'DateTimeOriginal','DateTimeDigitized','ShutterSpeedValue','ApertureValue',
      'ExposureBiasValue','MaxApertureValue','MeteringMode','Flash','FocalLength',
      'ColorSpace','PixelXDimension','PixelYDimension','FocalPlaneXResolution',
      'FocalPlaneYResolution','FocalPlaneResolutionUnit','SensingMethod','CustomRendered',
      'ExposureMode','WhiteBalance','DigitalZoomRatio','FocalLengthIn35mmFilm',
      'SceneCaptureType','GainControl','Contrast','Saturation','Sharpness',
      'SubjectDistanceRange','LensMake','LensModel'
    ]);
    const group = exifFields.has(key) ? 'EXIF' : 'Image';
    const oldVal = getFieldValue(group, key) ?? getFieldValue('Image', key);
    stagedChanges[key] = { old: oldVal, new: String(val), group };
  }
  updateStagedChanges();
  closeCascadeModalBtn();
  const count = userFields.length;
  const hasGps = !!lastAgentCascade._remove_gps;
  const hasMn  = !!lastAgentCascade._remove_makernote;
  showToast(
    `${count} fields staged! ${hasGps ? '(GPS will be removed)' : ''} ${hasMn ? '(MakerNote will be stripped)' : ''}`,
    'success'
  );
}

// ─── Forensic Diff ────────────────────────────
async function runForensicDiff() {
  if (!sessionId) return;

  document.getElementById('diff-card').style.display = 'block';
  document.getElementById('diff-results').innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted)">Analyzing...</div>';

  try {
    const res = await fetch(`${API}/api/forensic-diff`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    });
    const data = await res.json();
    renderForensicDiff(data);
  } catch (err) {
    document.getElementById('diff-results').innerHTML = `<div style="color:var(--red);padding:12px">Diff error: ${err.message}</div>`;
  }
}

function renderForensicDiff(data) {
  const { stealth_score, changed, added, removed, unchanged_count, total_fields, modified_count, change_percentage, risk_indicators } = data;

  const scoreColor = stealth_score >= 75 ? '#34d399' : stealth_score >= 50 ? '#fbbf24' : '#f87171';

  let html = `
    <div class="diff-score-wrap">
      <div class="diff-stealth" style="color:${scoreColor}">${stealth_score}<span style="font-size:1.5rem;opacity:0.6">/100</span></div>
      <div class="diff-stealth-label">Stealth Score</div>
    </div>
    <div class="diff-stats">
      <div class="diff-stat">
        <div class="diff-stat-num" style="color:var(--orange)">${changed.length}</div>
        <div class="diff-stat-label">Changed</div>
      </div>
      <div class="diff-stat">
        <div class="diff-stat-num" style="color:var(--red)">${removed.length}</div>
        <div class="diff-stat-label">Removed</div>
      </div>
      <div class="diff-stat">
        <div class="diff-stat-num" style="color:var(--green)">${added.length}</div>
        <div class="diff-stat-label">Added</div>
      </div>
    </div>`;

  // Risk indicators
  if (risk_indicators?.length) {
    html += risk_indicators.map(r => `
      <div class="risk-ind risk-ind-${r.severity}">
        <strong>${r.label}</strong>: ${escapeHtml(r.detail)}
      </div>`).join('');
  }

  // Changed fields table
  if (changed.length > 0) {
    html += `
      <div style="margin-top:12px;font-size:0.75rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Changed Fields</div>
      <table class="diff-table">
        <thead><tr><th>Field</th><th>Original</th><th>Modified</th></tr></thead>
        <tbody>
          ${changed.map(c => `
            <tr>
              <td class="diff-changed">${escapeHtml(c.field)}</td>
              <td style="color:var(--text-muted);text-decoration:line-through">${escapeHtml(c.old_value.substring(0,80))}</td>
              <td style="color:var(--cyan)">${escapeHtml(c.new_value.substring(0,80))}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  }

  if (removed.length > 0) {
    html += `
      <div style="margin-top:10px;font-size:0.75rem;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Removed Fields</div>
      ${removed.map(r => `<div class="diff-removed" style="font-size:0.8rem;padding:3px 0">— ${escapeHtml(r.field)}</div>`).join('')}`;
  }

  html += `<div style="margin-top:12px;font-size:0.78rem;color:var(--text-muted);text-align:right">${unchanged_count} fields unchanged · ${change_percentage}% modification rate</div>`;

  document.getElementById('diff-results').innerHTML = html;
}

// ─── Download ─────────────────────────────────
function downloadModified() {
  if (!currentOutputFile) {
    showToast('Apply changes first to generate modified image.', 'error'); return;
  }
  const a = document.createElement('a');
  a.href = `${API}/api/download/${currentOutputFile}`;
  a.download = `pixelveil_modified_${Date.now()}.jpg`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast('Downloading modified JPEG...', 'success');
}

// ─── Reset ────────────────────────────────────
function resetApp() {
  sessionId = null; originalMeta = null; currentMeta = null;
  stagedChanges = {}; currentOutputFile = null; lastAgentCascade = {};

  document.getElementById('editor-section').style.display = 'none';
  document.getElementById('upload-section').style.display = 'block';
  document.getElementById('upload-section').classList.add('active');
  document.getElementById('file-input').value = '';
  document.getElementById('agent-card').style.display = 'none';
  document.getElementById('diff-card').style.display = 'none';
  document.getElementById('diff-btn').style.display = 'none';
  document.getElementById('download-btn').style.display = 'none';
}

// ─── Toast ────────────────────────────────────
let toastTimer;
function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3200);
}
