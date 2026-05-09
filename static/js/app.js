/* ═══════════════════════════════════════════════════════════
   HACKFORGE WORKSPACE — MAIN APPLICATION JS
   SPA, Auth, Real-time, All Features
═══════════════════════════════════════════════════════════ */

'use strict';

// ── State ────────────────────────────────────────────────
const APP = {
  user: null,
  teams: [],
  currentTeam: null,
  currentProject: null,
  currentChannel: null,
  socket: null,
  editor: null,
  whiteboard: { tool: 'pen', color: '#00f5ff', size: 3, drawing: false },
  uploadQueue: [],
  currentPage: 'dashboard',
  cmdSelectedIndex: 0,
  otpEmail: null,
  otpPurpose: 'signup',
};

// ── API ──────────────────────────────────────────────────
const API = {
  base: '/api',
  async req(method, path, body = null, isForm = false) {
    const opts = { method, credentials: 'include', headers: {} };
    if (body && !isForm) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    if (body && isForm) { opts.body = body; }
    try {
      const res = await fetch(this.base + path, opts);
      const data = await res.json();
      return { ok: res.ok, status: res.status, data };
    } catch (e) { return { ok: false, data: { error: 'Network error' } }; }
  },
  get: (p) => API.req('GET', p),
  post: (p, b) => API.req('POST', p, b),
  patch: (p, b) => API.req('PATCH', p, b),
  put: (p, b) => API.req('PUT', p, b),
  del: (p) => API.req('DELETE', p),
  postForm: (p, fd) => API.req('POST', p, fd, true),
};

// ── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); showCommandPalette(); }
    if (e.key === 'Escape') { hideCommandPalette(); closeModal(); closeTeamPicker(); }
  });

  // Monaco editor setup
  require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs' } });

  // Auth check
  await initApp();
});

async function initApp() {
  const res = await API.get('/auth/me');
  if (res.ok) {
    APP.user = res.data.data.user;
    APP.teams = APP.user.memberships || [];
    if (APP.teams.length > 0) {
      const saved = sessionStorage.getItem('hf_team');
      const found = saved ? APP.teams.find(m => m.team_id === saved || (m.teams && m.teams.id === saved)) : null;
      setCurrentTeam(found || APP.teams[0]);
    }
    showApp();
  } else {
    showAuth();
  }
  hideLoader();
}

function hideLoader() {
  setTimeout(() => {
    const el = document.getElementById('loading-screen');
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.4s ease';
    setTimeout(() => el.remove(), 400);
  }, 1800);
}

// ── Auth UI ──────────────────────────────────────────────
function showAuth() {
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app').classList.add('hidden');
}
function showApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  updateSidebarUser();
  initSocket();
  loadDashboard();
}
function showPanel(id) {
  ['login-panel','signup-panel','otp-panel','forgot-panel'].forEach(p => {
    document.getElementById(p).classList.add('hidden');
  });
  document.getElementById(id).classList.remove('hidden');
}

function togglePassword(id) {
  const inp = document.getElementById(id);
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

function setAuthError(panelId, msg) {
  const el = document.getElementById(panelId);
  if (el) { el.textContent = msg; el.classList.remove('hidden'); }
}
function clearAuthError(panelId) {
  const el = document.getElementById(panelId);
  if (el) el.classList.add('hidden');
}

// ── Auth Actions ─────────────────────────────────────────
async function authLogin() {
  clearAuthError('login-error');
  const identifier = document.getElementById('login-identifier').value.trim();
  const password = document.getElementById('login-password').value;
  if (!identifier || !password) return setAuthError('login-error', 'Please fill all fields');

  const res = await API.post('/auth/login', { identifier, password });
  if (res.ok) {
    APP.user = res.data.data.user;
    const tRes = await API.get('/auth/me');
    if (tRes.ok) { APP.user = tRes.data.data.user; APP.teams = APP.user.memberships || []; }
    if (APP.teams.length) setCurrentTeam(APP.teams[0]);
    showApp();
    toast('Welcome back!', 'success');
  } else {
    setAuthError('login-error', res.data.error || 'Login failed');
  }
}

async function authSignup() {
  clearAuthError('signup-error');
  const displayName = document.getElementById('signup-displayname').value.trim();
  const username = document.getElementById('signup-username').value.trim();
  const email = document.getElementById('signup-email').value.trim().toLowerCase();
  const password = document.getElementById('signup-password').value;
  if (!displayName || !username || !email || !password) return setAuthError('signup-error', 'Please fill all fields');

  const res = await API.post('/auth/signup/initiate', { display_name: displayName, username, email, password });
  if (res.ok) {
    APP.otpEmail = email;
    APP.otpPurpose = 'signup';
    document.getElementById('otp-email-display').textContent = email;
    const otpDevEl = document.getElementById('otp-dev-display');
    if (otpDevEl) {
      otpDevEl.classList.add('hidden');
      otpDevEl.textContent = '';
    }
    // Dev OTP hint
    if (res.data.data && res.data.data.otp_dev) {
      if (otpDevEl) {
        otpDevEl.textContent = `Dev OTP: ${res.data.data.otp_dev}`;
        otpDevEl.classList.remove('hidden');
      }
      toast(`Dev OTP: ${res.data.data.otp_dev}`, 'info');
    }
    showPanel('otp-panel');
  } else {
    setAuthError('signup-error', res.data.error || 'Signup failed');
  }
}

async function authVerifyOTP() {
  clearAuthError('otp-error');
  const otp = [0,1,2,3,4,5].map(i => document.getElementById('otp'+i).value).join('');
  if (otp.length < 6) return setAuthError('otp-error', 'Please enter the full 6-digit code');

  const res = await API.post('/auth/signup/verify', { email: APP.otpEmail, otp });
  if (res.ok) {
    APP.user = res.data.data.user;
    const tRes = await API.get('/auth/me');
    if (tRes.ok) { APP.user = tRes.data.data.user; APP.teams = APP.user.memberships || []; }
    showApp();
    toast('Account created! Welcome to HackForge!', 'success');
    if (!APP.teams.length) setTimeout(showCreateTeamModal, 800);
  } else {
    setAuthError('otp-error', res.data.error || 'Verification failed');
  }
}

function otpMove(index) {
  const val = document.getElementById('otp'+index).value;
  if (val && index < 5) document.getElementById('otp'+(index+1)).focus();
  if (!val && index > 0) document.getElementById('otp'+(index-1)).focus();
}

async function resendOTP() {
  const res = await API.post('/auth/resend-otp', { email: APP.otpEmail, purpose: APP.otpPurpose });
  if (res.ok) {
    toast('OTP resent!', 'info');
    const otpDevEl = document.getElementById('otp-dev-display');
    if (res.data.data?.otp_dev) {
      if (otpDevEl) {
        otpDevEl.textContent = `Dev OTP: ${res.data.data.otp_dev}`;
        otpDevEl.classList.remove('hidden');
      }
      toast(`Dev OTP: ${res.data.data.otp_dev}`, 'info');
    }
  } else toast(res.data.error || 'Failed to resend', 'error');
}

async function authForgot() {
  const email = document.getElementById('forgot-email').value.trim();
  if (!email) return;
  const res = await API.post('/auth/forgot-password', { email });
  toast(res.data.message || 'Check your email', 'info');
}

async function authLogout() {
  await API.post('/auth/logout');
  APP.user = null; APP.teams = []; APP.currentTeam = null;
  if (APP.socket) APP.socket.disconnect();
  showAuth();
  showPanel('login-panel');
}

// ── Socket ───────────────────────────────────────────────
function initSocket() {
  if (APP.socket) return;
  APP.socket = io({ withCredentials: true });
  APP.socket.on('connect', () => {
    if (APP.currentTeam) APP.socket.emit('join_team', { team_id: APP.currentTeam.team_id || APP.currentTeam.id });
  });
  APP.socket.on('new_message', (data) => appendChatMessage(data));
  APP.socket.on('task_updated', () => loadTasks());
  APP.socket.on('whiteboard_draw', (data) => remoteWhiteboardDraw(data));
  APP.socket.on('presence_update', (data) => updatePresence(data));
  APP.socket.on('notification', (data) => {
    document.getElementById('notif-dot').style.display = 'block';
    toast(data.message || 'New notification', 'info');
  });
}

// ── Team Management ──────────────────────────────────────
function setCurrentTeam(membership) {
  APP.currentTeam = membership;
  const team = membership.teams || membership;
  const teamId = team.id || membership.team_id;
  sessionStorage.setItem('hf_team', teamId);
  document.getElementById('sidebar-team-name').textContent = team.name || 'Team';
  document.getElementById('sidebar-team-role').textContent = membership.role || 'member';
  const initials = (team.name || 'HF').substring(0, 2).toUpperCase();
  document.getElementById('sidebar-team-avatar').textContent = initials;
  if (APP.socket) {
    APP.socket.emit('join_team', { team_id: teamId });
  }
}

function updateSidebarUser() {
  if (!APP.user) return;
  document.getElementById('sidebar-username').textContent = APP.user.display_name || APP.user.username;
  if (APP.user.avatar_url) {
    document.getElementById('sidebar-user-avatar').src = APP.user.avatar_url;
  } else {
    document.getElementById('sidebar-user-avatar').src = `https://api.dicebear.com/7.x/identicon/svg?seed=${APP.user.username}`;
  }
}

function showTeamPicker() {
  const picker = document.getElementById('team-picker');
  if (!picker.classList.contains('hidden')) { closeTeamPicker(); return; }
  const list = document.getElementById('team-picker-list');
  list.innerHTML = '';
  APP.teams.forEach(m => {
    const team = m.teams || m;
    const div = document.createElement('div');
    div.className = `team-picker-item${APP.currentTeam === m ? ' active' : ''}`;
    div.innerHTML = `
      <div class="team-avatar" style="width:28px;height:28px;font-size:10px">${(team.name||'?').substring(0,2).toUpperCase()}</div>
      <div><div class="team-name">${team.name}</div><div class="team-role">${m.role}</div></div>
    `;
    div.onclick = () => { setCurrentTeam(m); closeTeamPicker(); loadDashboard(); };
    list.appendChild(div);
  });
  picker.classList.remove('hidden');
}
function closeTeamPicker() { document.getElementById('team-picker').classList.add('hidden'); }

// ── Navigation ───────────────────────────────────────────
function navigate(page) {
  APP.currentPage = page;
  document.querySelectorAll('.page').forEach(p => { p.classList.add('hidden'); p.classList.remove('active'); });
  const target = document.getElementById(`page-${page}`);
  if (target) { target.classList.remove('hidden'); target.classList.add('active'); }
  document.querySelectorAll('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.page === page);
  });
  document.getElementById('breadcrumb').textContent = page.charAt(0).toUpperCase() + page.slice(1);

  // Page-specific init
  const loaders = {
    dashboard: loadDashboard,
    tasks: loadTasks,
    chat: loadChat,
    files: loadFiles,
    members: loadMembers,
    ai: loadAIPage,
    settings: loadSettings,
    analytics: loadAnalytics,
    deployments: loadDeployments,
    wiki: loadWiki,
    meetings: loadMeetings,
    editor: initEditor,
    whiteboard: initWhiteboard,
    terminal: initTerminal,
  };
  if (loaders[page]) loaders[page]();
}

// ── Dashboard ────────────────────────────────────────────
async function loadDashboard() {
  if (!APP.currentTeam) return;
  const teamId = getTeamId();
  const [projRes, actRes, taskRes] = await Promise.all([
    API.get(`/teams/${teamId}/projects`),
    API.get(`/teams/${teamId}/activity?limit=20`),
    API.get(`/tasks?team_id=${teamId}&assignee_id=${APP.user.id}&limit=5`),
  ]);

  if (projRes.ok) renderProjects(projRes.data.data?.projects || []);
  if (actRes.ok) renderActivity(actRes.data.data?.activities || []);
  if (taskRes.ok) renderMyTasks(taskRes.data.data?.tasks || []);

  // Stats
  const projects = projRes.ok ? (projRes.data.data?.projects || []) : [];
  const tasks = taskRes.ok ? (taskRes.data.data?.tasks || []) : [];
  document.getElementById('stat-tasks').textContent = tasks.filter(t => t.status !== 'done').length;
  document.getElementById('stat-projects').textContent = projects.length;
  document.getElementById('stat-members').textContent = APP.currentTeam?.team_members_count || '?';

  // Storage
  const teamInfo = APP.currentTeam?.teams || APP.currentTeam;
  const usedMB = parseFloat(teamInfo?.storage_used_mb || 0).toFixed(0);
  document.getElementById('stat-storage').textContent = `${usedMB} MB`;

  // Populate project select for tasks page
  const sel = document.getElementById('task-project-select');
  sel.innerHTML = '<option value="">All Projects</option>';
  projects.forEach(p => sel.innerHTML += `<option value="${p.id}">${p.name}</option>`);
}

function renderProjects(projects) {
  const el = document.getElementById('projects-list');
  if (!projects.length) { el.innerHTML = '<div class="empty-state"><i class="fas fa-rocket"></i><p>No projects yet. Create your first project.</p></div>'; return; }
  const colors = ['#00f5ff','#a855f7','#22c55e','#f97316','#ec4899','#eab308'];
  el.innerHTML = projects.map((p, i) => `
    <div class="project-card" onclick="selectProject('${p.id}','${p.name}')">
      <div class="project-color" style="background:${colors[i%colors.length]}"></div>
      <div class="project-info">
        <div class="project-name">${escHtml(p.name)}</div>
        <div class="project-meta">${p.description ? escHtml(p.description.substring(0,50)) : 'No description'}</div>
      </div>
      <div class="project-status">${p.status || 'active'}</div>
    </div>
  `).join('');
}

function renderActivity(items) {
  const el = document.getElementById('activity-feed');
  if (!items.length) { el.innerHTML = '<div class="empty-state"><i class="fas fa-stream"></i><p>No activity yet</p></div>'; return; }
  el.innerHTML = items.map(a => `
    <div class="activity-item">
      <img class="activity-avatar" src="${userAvatar(a.user)}" alt="avatar" />
      <div>
        <div class="activity-text"><strong>${escHtml(a.user?.display_name || 'Someone')}</strong> ${escHtml(a.description || a.action)}</div>
        <div class="activity-time">${timeAgo(a.created_at)}</div>
      </div>
    </div>
  `).join('');
}

function renderMyTasks(tasks) {
  const el = document.getElementById('my-tasks-list');
  if (!tasks.length) { el.innerHTML = '<div class="empty-state"><i class="fas fa-check-circle"></i><p>No tasks assigned to you</p></div>'; return; }
  el.innerHTML = tasks.map(t => `
    <div class="task-row" onclick="showTaskDetail('${t.id}')">
      <div class="task-priority ${t.priority}"></div>
      <div class="task-row-title">${escHtml(t.title)}</div>
      <div class="task-row-status">${t.status}</div>
    </div>
  `).join('');
}

// ── Tasks ────────────────────────────────────────────────
async function loadTasks() {
  const projectId = document.getElementById('task-project-select')?.value;
  const teamId = getTeamId();
  const params = projectId ? `project_id=${projectId}` : `team_id=${teamId}`;
  const res = await API.get(`/tasks?${params}`);
  if (!res.ok) return;
  const tasks = res.data.data?.tasks || [];
  ['todo','in_progress','review','done'].forEach(s => {
    document.getElementById(`tasks-${s}`).innerHTML = '';
    document.getElementById(`count-${s}`).textContent = 0;
  });
  tasks.forEach(renderTaskCard);
}

function renderTaskCard(task) {
  const col = document.getElementById(`tasks-${task.status}`);
  if (!col) return;
  const card = document.createElement('div');
  card.className = 'task-card';
  card.draggable = true;
  card.dataset.taskId = task.id;
  card.innerHTML = `
    <div class="task-card-title">${escHtml(task.title)}</div>
    <div class="task-card-meta">
      <span class="task-tag">${task.priority || 'medium'}</span>
      ${task.assignee ? `<img class="task-assignee" src="${userAvatar(task.assignee)}" title="${task.assignee.display_name}" alt="avatar" />` : ''}
      ${task.due_date ? `<span class="task-due">${formatDate(task.due_date)}</span>` : ''}
    </div>
  `;
  card.addEventListener('dragstart', () => { card.classList.add('dragging'); card.dataset.originalStatus = task.status; });
  card.addEventListener('dragend', () => card.classList.remove('dragging'));
  card.addEventListener('click', () => showTaskDetail(task.id));
  col.appendChild(card);
  const countEl = document.getElementById(`count-${task.status}`);
  if (countEl) countEl.textContent = parseInt(countEl.textContent) + 1;
}

function dragOver(e) { e.preventDefault(); e.currentTarget.classList.add('drag-over'); }
function dropTask(e, newStatus) {
  e.preventDefault();
  e.currentTarget.classList.remove('drag-over');
  const dragging = document.querySelector('.task-card.dragging');
  if (!dragging) return;
  const taskId = dragging.dataset.taskId;
  API.patch(`/tasks/${taskId}`, { status: newStatus }).then(res => {
    if (res.ok) { loadTasks(); if (APP.socket) APP.socket.emit('task_update', { team_id: getTeamId() }); }
  });
}

// ── Task Modals ──────────────────────────────────────────
function showCreateTaskModal(defaultStatus = 'todo') {
  const teamId = getTeamId();
  const projectId = document.getElementById('task-project-select')?.value || '';
  openModal('Create Task', `
    <div class="form-group"><label>Title</label><input type="text" id="task-title" class="neon-input" placeholder="Task title..." /></div>
    <div class="form-group"><label>Description</label><textarea id="task-desc" class="neon-input" rows="3" placeholder="Describe the task..."></textarea></div>
    <div class="form-row">
      <div class="form-group"><label>Priority</label>
        <select id="task-priority" class="neon-select" style="width:100%">
          <option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option>
        </select>
      </div>
      <div class="form-group"><label>Status</label>
        <select id="task-status" class="neon-select" style="width:100%">
          <option value="todo" ${defaultStatus==='todo'?'selected':''}>To Do</option>
          <option value="in_progress" ${defaultStatus==='in_progress'?'selected':''}>In Progress</option>
          <option value="review" ${defaultStatus==='review'?'selected':''}>Review</option>
          <option value="done" ${defaultStatus==='done'?'selected':''}>Done</option>
        </select>
      </div>
    </div>
    <div class="form-group"><label>Due Date</label><input type="date" id="task-due" class="neon-input" /></div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitCreateTask('${teamId}','${projectId}')">Create Task</button>
    </div>
  `);
}

async function submitCreateTask(teamId, projectId) {
  const title = document.getElementById('task-title').value.trim();
  if (!title) return toast('Task title required', 'error');
  const body = {
    title,
    description: document.getElementById('task-desc').value,
    priority: document.getElementById('task-priority').value,
    status: document.getElementById('task-status').value,
    due_date: document.getElementById('task-due').value || null,
    project_id: projectId || null,
    team_id: teamId,
  };
  const res = await API.post('/tasks', body);
  if (res.ok) { closeModal(); loadTasks(); toast('Task created!', 'success'); }
  else toast(res.data.error || 'Failed to create task', 'error');
}

async function showTaskDetail(taskId) {
  const res = await API.get(`/tasks/${taskId}`);
  if (!res.ok) return;
  const t = res.data.data.task;
  const commentsRes = await API.get(`/tasks/${taskId}/comments`);
  const comments = commentsRes.ok ? (commentsRes.data.data?.comments || []) : [];

  openModal(`Task: ${t.title}`, `
    <div style="margin-bottom:12px">
      <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px">${escHtml(t.description || 'No description')}</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <span class="task-tag">${t.priority}</span>
        <span class="task-row-status">${t.status}</span>
        ${t.due_date ? `<span class="task-due"><i class="fas fa-calendar"></i> ${formatDate(t.due_date)}</span>` : ''}
      </div>
    </div>
    <div style="margin-top:16px">
      <div style="font-size:12px;font-weight:700;color:var(--text-muted);margin-bottom:10px;text-transform:uppercase;letter-spacing:1px">Comments</div>
      <div id="task-comments-list" style="display:flex;flex-direction:column;gap:8px;max-height:200px;overflow-y:auto;margin-bottom:12px">
        ${comments.map(c => `
          <div style="display:flex;gap:8px;padding:8px;background:rgba(255,255,255,0.02);border-radius:6px">
            <img src="${userAvatar(c.user)}" style="width:24px;height:24px;border-radius:50%;" alt="avatar"/>
            <div>
              <div style="font-size:11px;font-weight:700">${escHtml(c.user?.display_name || 'User')}</div>
              <div style="font-size:12px;color:var(--text-secondary)">${escHtml(c.content)}</div>
            </div>
          </div>
        `).join('')}
        ${!comments.length ? '<div class="empty-sm">No comments yet</div>' : ''}
      </div>
      <div style="display:flex;gap:8px">
        <input type="text" id="task-comment-input" class="neon-input" placeholder="Add a comment..." style="flex:1" onkeydown="if(event.key==='Enter')submitComment('${taskId}')" />
        <button class="btn-secondary" onclick="submitComment('${taskId}')">Post</button>
      </div>
    </div>
  `);
}

async function submitComment(taskId) {
  const content = document.getElementById('task-comment-input').value.trim();
  if (!content) return;
  const res = await API.post(`/tasks/${taskId}/comments`, { content });
  if (res.ok) { closeModal(); showTaskDetail(taskId); }
  else toast(res.data.error || 'Failed to add comment', 'error');
}

// ── Chat ─────────────────────────────────────────────────
async function loadChat() {
  if (!APP.currentTeam) return;
  const teamId = getTeamId();
  const res = await API.get(`/chat/rooms?team_id=${teamId}`);
  const rooms = res.ok ? (res.data.data?.rooms || []) : [];
  const list = document.getElementById('channels-list');
  list.innerHTML = '';
  rooms.filter(r => r.type === 'channel').forEach(r => {
    const item = document.createElement('div');
    item.className = `channel-item${APP.currentChannel?.id === r.id ? ' active' : ''}`;
    item.innerHTML = `<span class="channel-hash">#</span><span>${escHtml(r.name)}</span>`;
    item.onclick = () => selectChannel(r);
    list.appendChild(item);
  });
  if (rooms.length && !APP.currentChannel) selectChannel(rooms[0]);
}

async function selectChannel(room) {
  APP.currentChannel = room;
  document.getElementById('active-channel-name').textContent = room.name;
  document.querySelectorAll('.channel-item').forEach(el => el.classList.toggle('active', el.querySelector('span:last-child')?.textContent === room.name));
  const res = await API.get(`/chat/rooms/${room.id}/messages?limit=50`);
  const messages = res.ok ? (res.data.data?.messages || []) : [];
  const container = document.getElementById('chat-messages');
  container.innerHTML = '';
  messages.forEach(m => appendChatMessage(m, false));
  container.scrollTop = container.scrollHeight;
  if (APP.socket) APP.socket.emit('join_room', { room_id: room.id });
}

function appendChatMessage(msg, scroll = true) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg';
  div.innerHTML = `
    <img class="chat-msg-avatar" src="${userAvatar(msg.user || msg.sender)}" alt="avatar" />
    <div class="chat-msg-body">
      <div class="chat-msg-header">
        <span class="chat-msg-user">${escHtml(msg.user?.display_name || msg.sender?.display_name || 'User')}</span>
        <span class="chat-msg-time">${timeAgo(msg.created_at || new Date().toISOString())}</span>
      </div>
      <div class="chat-msg-text">${escHtml(msg.content)}</div>
    </div>
  `;
  container.appendChild(div);
  if (scroll) container.scrollTop = container.scrollHeight;
}

async function sendChatMessage() {
  const el = document.getElementById('chat-input');
  const content = el.textContent.trim();
  if (!content || !APP.currentChannel) return;
  el.textContent = '';
  const res = await API.post(`/chat/rooms/${APP.currentChannel.id}/messages`, { content });
  if (!res.ok) toast('Failed to send message', 'error');
}

function chatKeydown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); } }

// ── Files ────────────────────────────────────────────────
async function loadFiles() {
  if (!APP.currentTeam) return;
  const teamId = getTeamId();
  const res = await API.get(`/storage/files?team_id=${teamId}`);
  const files = res.ok ? (res.data.data?.files || []) : [];
  renderFilesGrid(files);
}

function renderFilesGrid(files) {
  const grid = document.getElementById('files-grid');
  if (!files.length) { grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><i class="fas fa-folder-open"></i><p>No files yet. Upload your first file!</p></div>'; return; }
  grid.innerHTML = files.map(f => `
    <div class="file-card" onclick="openFile('${f.id}')">
      <div class="file-icon">${getFileIcon(f.filename)}</div>
      <div class="file-name">${escHtml(f.filename || f.original_name)}</div>
      <div class="file-size">${formatBytes(f.size_bytes)}</div>
      <div class="file-actions">
        <button class="icon-btn sm" onclick="event.stopPropagation();downloadFile('${f.id}')" title="Download"><i class="fas fa-download"></i></button>
        <button class="icon-btn sm danger" onclick="event.stopPropagation();deleteFile('${f.id}')" title="Delete"><i class="fas fa-trash"></i></button>
      </div>
    </div>
  `).join('');
}

function getFileIcon(name) {
  if (!name) return '📄';
  const ext = name.split('.').pop().toLowerCase();
  const icons = { jpg:'🖼️', jpeg:'🖼️', png:'🖼️', gif:'🖼️', webp:'🖼️', svg:'🎨', pdf:'📕', doc:'📝', docx:'📝', txt:'📄', md:'📝', py:'🐍', js:'📜', ts:'📘', html:'🌐', css:'🎨', json:'⚙️', zip:'🗜️', tar:'🗜️', gz:'🗜️', mp4:'🎬', mp3:'🎵', csv:'📊', xlsx:'📊' };
  return icons[ext] || '📄';
}

function setFileView(mode) {
  document.getElementById('view-grid').classList.toggle('active', mode === 'grid');
  document.getElementById('view-list').classList.toggle('active', mode === 'list');
  const grid = document.getElementById('files-grid');
  if (mode === 'list') grid.style.gridTemplateColumns = '1fr';
  else grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(160px, 1fr))';
}

function fileDragOver(e) {
  e.preventDefault();
  document.getElementById('drop-overlay').classList.remove('hidden');
}
function fileDragLeave() { document.getElementById('drop-overlay').classList.add('hidden'); }
function fileDropped(e) {
  e.preventDefault();
  document.getElementById('drop-overlay').classList.add('hidden');
  const files = e.dataTransfer.files;
  if (files.length) { showUploadModal(); setTimeout(() => filesSelected(files), 100); }
}

async function downloadFile(fileId) {
  const res = await API.get(`/storage/files/${fileId}/download`);
  if (res.ok && res.data.data?.url) {
    const a = document.createElement('a'); a.href = res.data.data.url; a.target = '_blank'; a.click();
  } else toast('Download failed', 'error');
}

async function deleteFile(fileId) {
  if (!confirm('Delete this file?')) return;
  const res = await API.del(`/storage/files/${fileId}`);
  if (res.ok) { toast('File deleted', 'success'); loadFiles(); }
  else toast('Delete failed', 'error');
}

// ── Upload ────────────────────────────────────────────────
function showUploadModal() {
  APP.uploadQueue = [];
  document.getElementById('upload-queue').innerHTML = '';
  document.getElementById('upload-start-btn').disabled = true;
  document.getElementById('upload-modal').classList.remove('hidden');
  document.getElementById('modal-overlay').classList.remove('hidden');
}
function closeUploadModal() {
  document.getElementById('upload-modal').classList.add('hidden');
  document.getElementById('modal-overlay').classList.add('hidden');
}
function triggerUploadInput() { document.getElementById('upload-input').click(); }
function uploadDragOver(e) { e.preventDefault(); e.currentTarget.classList.add('drag-active'); }
function uploadDragLeave(e) { e.currentTarget.classList.remove('drag-active'); }
function uploadDropped(e) { e.preventDefault(); e.currentTarget.classList.remove('drag-active'); filesSelected(e.dataTransfer.files); }

function filesSelected(fileList) {
  Array.from(fileList).forEach(file => {
    APP.uploadQueue.push({ file, progress: 0, status: 'pending' });
    const idx = APP.uploadQueue.length - 1;
    const item = document.createElement('div');
    item.className = 'upload-item';
    item.id = `upload-item-${idx}`;
    item.innerHTML = `
      <div class="upload-item-icon">${getFileIcon(file.name)}</div>
      <div class="upload-item-info">
        <div class="upload-item-name">${escHtml(file.name)}</div>
        <div class="upload-item-size">${formatBytes(file.size)}</div>
        <div class="upload-progress"><div class="upload-progress-bar" id="prog-${idx}" style="width:0%"></div></div>
      </div>
    `;
    document.getElementById('upload-queue').appendChild(item);
  });
  document.getElementById('upload-start-btn').disabled = APP.uploadQueue.length === 0;
}

async function startUploads() {
  const teamId = getTeamId();
  for (let i = 0; i < APP.uploadQueue.length; i++) {
    const item = APP.uploadQueue[i];
    if (item.status !== 'pending') continue;
    const fd = new FormData();
    fd.append('file', item.file);
    fd.append('team_id', teamId);
    if (APP.currentProject) fd.append('project_id', APP.currentProject.id);

    // Simulate progress
    const progEl = document.getElementById(`prog-${i}`);
    const sim = setInterval(() => {
      item.progress = Math.min(item.progress + 10, 85);
      if (progEl) progEl.style.width = item.progress + '%';
    }, 150);

    const res = await API.postForm('/storage/upload', fd);
    clearInterval(sim);
    if (progEl) progEl.style.width = '100%';
    item.status = res.ok ? 'done' : 'error';
  }
  toast('Uploads complete!', 'success');
  setTimeout(() => { closeUploadModal(); loadFiles(); }, 600);
}

// ── AI ───────────────────────────────────────────────────
function loadAIPage() { loadAIMemory(); }

async function sendAIMessage() {
  const input = document.getElementById('ai-input');
  const msg = input.value.trim();
  if (!msg) return;
  aiPrompt(msg);
  input.value = '';
  autoResize(input);
}

async function aiPrompt(msg) {
  const container = document.getElementById('ai-messages');
  // Remove welcome if present
  const welcome = container.querySelector('.ai-welcome');
  if (welcome) welcome.remove();

  // User message
  const userDiv = document.createElement('div');
  userDiv.className = 'ai-msg user';
  userDiv.innerHTML = `
    <div class="ai-msg-avatar"><i class="fas fa-user"></i></div>
    <div class="ai-msg-content">${escHtml(msg)}</div>
  `;
  container.appendChild(userDiv);
  container.scrollTop = container.scrollHeight;

  // Typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'ai-msg bot';
  typingDiv.id = 'ai-typing';
  typingDiv.innerHTML = `
    <div class="ai-msg-avatar"><i class="fas fa-brain"></i></div>
    <div class="ai-msg-content" style="color:var(--text-muted)">Thinking<span class="dots">...</span></div>
  `;
  container.appendChild(typingDiv);
  container.scrollTop = container.scrollHeight;

  const mode = document.getElementById('ai-mode-select').value;
  const teamId = getTeamId();
  const res = await API.post('/ai/chat', { message: msg, mode, team_id: teamId });

  typingDiv.remove();
  const botDiv = document.createElement('div');
  botDiv.className = 'ai-msg bot';
  const responseText = res.ok ? (res.data.data?.response || res.data.data?.text || 'No response') : 'AI service unavailable. Please check your API key.';
  botDiv.innerHTML = `
    <div class="ai-msg-avatar"><i class="fas fa-brain"></i></div>
    <div class="ai-msg-content">${marked.parse ? marked.parse(responseText) : escHtml(responseText)}</div>
  `;
  container.appendChild(botDiv);
  container.scrollTop = container.scrollHeight;
}

function aiKeydown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAIMessage(); } }
function clearAIChat() {
  document.getElementById('ai-messages').innerHTML = `
    <div class="ai-welcome">
      <div class="ai-avatar-large"><i class="fas fa-brain"></i></div>
      <h3>HackForge AI Copilot</h3>
      <p>Powered by Google Gemini. Ask me anything about your project.</p>
    </div>`;
}
function autoResize(ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'; }

async function loadAIMemory() {
  const teamId = getTeamId();
  const res = await API.get(`/ai/memory?team_id=${teamId}`);
  const memories = res.ok ? (res.data.data?.memories || []) : [];
  const el = document.getElementById('ai-memory-list');
  if (!memories.length) { el.innerHTML = '<div class="empty-sm">No memories yet</div>'; return; }
  el.innerHTML = memories.slice(0, 10).map(m => `
    <div class="memory-item">${escHtml(m.content?.substring(0, 80) || m.summary || 'Memory entry')}</div>
  `).join('');
}

// ── Members ───────────────────────────────────────────────
async function loadMembers() {
  const teamId = getTeamId();
  const res = await API.get(`/teams/${teamId}/members`);
  const members = res.ok ? (res.data.data?.members || []) : [];
  const grid = document.getElementById('members-grid');
  if (!members.length) { grid.innerHTML = '<div class="empty-state"><i class="fas fa-users"></i><p>No members yet</p></div>'; return; }
  grid.innerHTML = members.map(m => `
    <div class="member-card">
      <img class="member-avatar" src="${userAvatar(m.user || m)}" alt="avatar" />
      <div class="member-name">${escHtml(m.user?.display_name || m.display_name || 'Member')}</div>
      <div class="member-role">${m.role}</div>
      ${m.user?.skills?.length ? `<div class="member-skills">${m.user.skills.slice(0,4).map(s=>`<span class="skill-tag">${escHtml(s)}</span>`).join('')}</div>` : ''}
    </div>
  `).join('');
}

function showInviteModal() {
  const teamId = getTeamId();
  openModal('Invite Member', `
    <p style="color:var(--text-secondary);font-size:13px;margin-bottom:16px">Invite someone to your team by email.</p>
    <div class="form-group"><label>Email</label><input type="email" id="invite-email" class="neon-input" placeholder="member@example.com" /></div>
    <div class="form-group"><label>Role</label>
      <select id="invite-role" class="neon-select" style="width:100%">
        <option value="developer">Developer</option>
        <option value="designer">Designer</option>
        <option value="viewer">Viewer</option>
        <option value="admin">Admin</option>
      </select>
    </div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitInvite('${teamId}')">Send Invite</button>
    </div>
  `);
}

async function submitInvite(teamId) {
  const email = document.getElementById('invite-email').value.trim();
  const role = document.getElementById('invite-role').value;
  if (!email) return;
  const res = await API.post(`/teams/${teamId}/invite`, { email, role });
  if (res.ok) { closeModal(); toast('Invitation sent!', 'success'); }
  else toast(res.data.error || 'Failed to invite', 'error');
}

// ── Settings ──────────────────────────────────────────────
function loadSettings() {
  if (!APP.user) return;
  document.getElementById('prf-displayname').value = APP.user.display_name || '';
  document.getElementById('prf-bio').value = APP.user.bio || '';
  document.getElementById('prf-github').value = APP.user.github_url || '';
  document.getElementById('prf-portfolio').value = APP.user.portfolio_url || '';
  document.getElementById('prf-skills').value = (APP.user.skills || []).join(', ');
  const team = APP.currentTeam?.teams || {};
  document.getElementById('team-name-input').value = team.name || '';
  document.getElementById('team-desc-input').value = team.description || '';
  document.getElementById('team-joincode').value = team.join_code || '';
  loadAuditLogs();
}

function showSettingsTab(tab) {
  document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.settings-link').forEach(l => l.classList.remove('active'));
  document.getElementById(`settings-${tab}`).classList.add('active');
  event.currentTarget.classList.add('active');
}

async function saveProfile() {
  const body = {
    display_name: document.getElementById('prf-displayname').value.trim(),
    bio: document.getElementById('prf-bio').value.trim(),
    github_url: document.getElementById('prf-github').value.trim(),
    portfolio_url: document.getElementById('prf-portfolio').value.trim(),
    skills: document.getElementById('prf-skills').value.split(',').map(s => s.trim()).filter(Boolean),
  };
  const res = await API.patch('/auth/me', body);
  if (res.ok) { APP.user = res.data.data.user; updateSidebarUser(); toast('Profile saved!', 'success'); }
  else toast(res.data.error || 'Failed to save', 'error');
}

async function saveTeamSettings() {
  const teamId = getTeamId();
  const body = {
    name: document.getElementById('team-name-input').value.trim(),
    description: document.getElementById('team-desc-input').value.trim(),
  };
  const res = await API.patch(`/teams/${teamId}`, body);
  if (res.ok) toast('Team settings saved!', 'success');
  else toast(res.data.error || 'Failed to save', 'error');
}

function copyJoinCode() {
  const code = document.getElementById('team-joincode').value;
  navigator.clipboard.writeText(code).then(() => toast('Join code copied!', 'info'));
}

async function changePassword() {
  const current = document.getElementById('sec-current').value;
  const newPwd = document.getElementById('sec-new').value;
  if (!current || !newPwd) return toast('Fill all fields', 'error');
  const res = await API.post('/auth/change-password', { current_password: current, new_password: newPwd });
  if (res.ok) toast('Password updated!', 'success');
  else toast(res.data.error || 'Failed', 'error');
}

async function logoutAllDevices() {
  await API.post('/auth/logout-all');
  authLogout();
}

async function loadAuditLogs() {
  const teamId = getTeamId();
  const res = await API.get(`/teams/${teamId}/audit?limit=20`);
  const logs = res.ok ? (res.data.data?.logs || []) : [];
  const el = document.getElementById('audit-logs-list');
  if (!logs.length) { el.innerHTML = '<div class="empty-sm">No audit logs yet</div>'; return; }
  el.innerHTML = logs.map(l => `
    <div class="audit-item">
      <div class="audit-action">${escHtml(l.action)}</div>
      <div class="audit-ip">${l.ip_address || '—'}</div>
      <div class="audit-time">${timeAgo(l.created_at)}</div>
    </div>
  `).join('');
}

// ── Deployments ──────────────────────────────────────────
async function loadDeployments() {
  const teamId = getTeamId();
  const res = await API.get(`/deployments?team_id=${teamId}`);
  const deploys = res.ok ? (res.data.data?.deployments || []) : [];
  const el = document.getElementById('deployments-list');
  if (!deploys.length) {
    el.innerHTML = `<div class="glass-panel" style="padding:40px;text-align:center">
      <div class="empty-state"><i class="fas fa-rocket"></i><p>No deployments yet. Deploy your first project!</p></div>
    </div>`;
    return;
  }
  el.innerHTML = deploys.map(d => `
    <div class="deploy-card">
      <div class="deploy-status ${d.status}"></div>
      <div class="deploy-info">
        <div class="deploy-name">${escHtml(d.project_name || d.name || 'Deployment')}</div>
        <div class="deploy-meta">${timeAgo(d.created_at)} · ${escHtml(d.commit_msg || '')}</div>
      </div>
      <div class="deploy-platform">${d.platform || 'Manual'}</div>
      ${d.url ? `<a href="${d.url}" target="_blank" class="btn-ghost sm"><i class="fas fa-external-link-alt"></i> View</a>` : ''}
    </div>
  `).join('');
}

function showDeployModal() {
  const teamId = getTeamId();
  openModal('Deploy Project', `
    <div class="form-group"><label>Project Name</label><input type="text" id="dep-name" class="neon-input" placeholder="my-project" /></div>
    <div class="form-group"><label>Platform</label>
      <select id="dep-platform" class="neon-select" style="width:100%">
        <option value="netlify">Netlify</option>
        <option value="railway">Railway</option>
        <option value="github_pages">GitHub Pages</option>
        <option value="manual">Manual</option>
      </select>
    </div>
    <div class="form-group"><label>Build Command</label><input type="text" id="dep-build" class="neon-input" placeholder="npm run build" /></div>
    <div class="form-group"><label>Publish Dir</label><input type="text" id="dep-dir" class="neon-input" placeholder="dist" /></div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitDeploy('${teamId}')"><i class="fas fa-rocket"></i> Deploy Now</button>
    </div>
  `);
}

async function submitDeploy(teamId) {
  const body = {
    project_name: document.getElementById('dep-name').value.trim(),
    platform: document.getElementById('dep-platform').value,
    build_command: document.getElementById('dep-build').value.trim(),
    publish_dir: document.getElementById('dep-dir').value.trim(),
    team_id: teamId,
  };
  const res = await API.post('/deployments', body);
  if (res.ok) { closeModal(); loadDeployments(); toast('Deployment started!', 'success'); }
  else toast(res.data.error || 'Deploy failed', 'error');
}

// ── Analytics ─────────────────────────────────────────────
function loadAnalytics() {
  const ctx1 = document.getElementById('chart-tasks').getContext('2d');
  new Chart(ctx1, { type: 'line', data: {
    labels: ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
    datasets: [{ label: 'Completed', data: [3,5,2,8,6,4,7], borderColor: '#00f5ff', backgroundColor: 'rgba(0,245,255,0.1)', tension: 0.4, fill: true }]
  }, options: { responsive: true, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } } } } });

  const ctx2 = document.getElementById('chart-members').getContext('2d');
  new Chart(ctx2, { type: 'bar', data: {
    labels: APP.teams.slice(0,6).map(m => m.user?.display_name?.split(' ')[0] || 'Member'),
    datasets: [{ label: 'Actions', data: [12,8,20,5,15,9], backgroundColor: 'rgba(168,85,247,0.6)', borderColor: '#a855f7', borderWidth: 1 }]
  }, options: { responsive: true, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } } } } });

  const ctx3 = document.getElementById('chart-storage').getContext('2d');
  new Chart(ctx3, { type: 'doughnut', data: {
    labels: ['Used', 'Free'],
    datasets: [{ data: [35, 65], backgroundColor: ['rgba(0,245,255,0.7)', 'rgba(255,255,255,0.05)'], borderColor: ['#00f5ff', 'rgba(255,255,255,0.1)'], borderWidth: 1 }]
  }, options: { responsive: true, plugins: { legend: { labels: { color: '#94a3b8' } } } } });

  const ctx4 = document.getElementById('chart-deployments').getContext('2d');
  new Chart(ctx4, { type: 'bar', data: {
    labels: ['Week 1','Week 2','Week 3','Week 4'],
    datasets: [{ label: 'Success', data: [4,6,3,8], backgroundColor: 'rgba(34,197,94,0.6)', borderColor: '#22c55e', borderWidth: 1 },
               { label: 'Failed', data: [1,0,2,0], backgroundColor: 'rgba(239,68,68,0.6)', borderColor: '#ef4444', borderWidth: 1 }]
  }, options: { responsive: true, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } } } } });
}

// ── Wiki ──────────────────────────────────────────────────
async function loadWiki() {
  const teamId = getTeamId();
  const res = await API.get(`/wiki?team_id=${teamId}`);
  const pages = res.ok ? (res.data.data?.pages || []) : [];
  const list = document.getElementById('wiki-pages-list');
  list.innerHTML = '';
  pages.forEach(p => {
    const item = document.createElement('div');
    item.className = 'wiki-page-item';
    item.textContent = p.title;
    item.onclick = () => openWikiPage(p);
    list.appendChild(item);
  });
}

function openWikiPage(page) {
  document.querySelectorAll('.wiki-page-item').forEach(el => el.classList.toggle('active', el.textContent === page.title));
  document.getElementById('wiki-editor-area').innerHTML = `
    <div style="margin-bottom:12px;display:flex;align-items:center;justify-content:space-between">
      <h2 style="font-family:var(--font-title);font-size:20px">${escHtml(page.title)}</h2>
      <button class="btn-secondary" onclick="editWikiPage('${page.id}')"><i class="fas fa-edit"></i> Edit</button>
    </div>
    <div style="color:var(--text-secondary);font-size:13px;line-height:1.8">
      ${marked.parse ? marked.parse(page.content || '') : escHtml(page.content || 'No content')}
    </div>
  `;
}

function showCreateWikiModal() {
  const teamId = getTeamId();
  openModal('Create Wiki Page', `
    <div class="form-group"><label>Title</label><input type="text" id="wiki-title" class="neon-input" placeholder="Page title..." /></div>
    <div class="form-group"><label>Content (Markdown)</label><textarea id="wiki-content" class="neon-input" rows="8" placeholder="Write in Markdown..."></textarea></div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitWikiPage('${teamId}')">Create Page</button>
    </div>
  `);
}

async function submitWikiPage(teamId) {
  const title = document.getElementById('wiki-title').value.trim();
  const content = document.getElementById('wiki-content').value;
  if (!title) return;
  const res = await API.post('/wiki', { title, content, team_id: teamId });
  if (res.ok) { closeModal(); loadWiki(); toast('Page created!', 'success'); }
  else toast(res.data.error || 'Failed', 'error');
}

// ── Meetings ──────────────────────────────────────────────
async function loadMeetings() {
  const teamId = getTeamId();
  const res = await API.get(`/meetings?team_id=${teamId}`);
  const meetings = res.ok ? (res.data.data?.meetings || []) : [];
  const grid = document.getElementById('meetings-grid');
  if (!meetings.length) {
    grid.innerHTML = `<div class="glass-panel" style="padding:40px;text-align:center">
      <div class="empty-state"><i class="fas fa-video"></i><p>No meetings yet. Start or schedule one!</p></div>
    </div>`;
    return;
  }
  grid.innerHTML = meetings.map(m => `
    <div class="meeting-card">
      <div style="font-size:14px;font-weight:700;margin-bottom:8px">${escHtml(m.title)}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:12px">${timeAgo(m.starts_at)} · ${m.participants_count || 0} participants</div>
      ${m.jitsi_url ? `<a href="${m.jitsi_url}" target="_blank" class="btn-primary" style="font-size:12px;display:inline-flex"><i class="fas fa-video"></i> Join Meeting</a>` : ''}
    </div>
  `).join('');
}

async function startInstantMeeting() {
  const teamId = getTeamId();
  const roomName = `hackforge-${teamId}-${Date.now()}`;
  const jitsiUrl = `https://meet.jit.si/${roomName}`;
  window.open(jitsiUrl, '_blank');
  const res = await API.post('/meetings', { title: 'Quick Meeting', team_id: teamId, jitsi_url: jitsiUrl, starts_at: new Date().toISOString() });
  if (res.ok) loadMeetings();
}

// ── Whiteboard ────────────────────────────────────────────
function initWhiteboard() {
  const canvas = document.getElementById('whiteboard-canvas');
  const ctx = canvas.getContext('2d');
  const resizeCanvas = () => {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width; canvas.height = rect.height || 500;
  };
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  let lastX, lastY;
  const wb = APP.whiteboard;

  canvas.addEventListener('mousedown', (e) => {
    wb.drawing = true;
    [lastX, lastY] = [e.offsetX, e.offsetY];
    if (wb.tool === 'text') {
      const text = prompt('Enter text:');
      if (text) { ctx.fillStyle = wb.color; ctx.font = '16px DM Sans'; ctx.fillText(text, e.offsetX, e.offsetY); emitDraw({ type: 'text', text, x: e.offsetX, y: e.offsetY, color: wb.color }); }
      wb.drawing = false;
    }
  });
  canvas.addEventListener('mousemove', (e) => {
    if (!wb.drawing) return;
    if (wb.tool === 'pen' || wb.tool === 'eraser') {
      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(e.offsetX, e.offsetY);
      ctx.strokeStyle = wb.tool === 'eraser' ? '#0a0f1a' : wb.color;
      ctx.lineWidth = wb.size;
      ctx.lineCap = 'round';
      ctx.stroke();
      emitDraw({ type: 'line', x1: lastX, y1: lastY, x2: e.offsetX, y2: e.offsetY, color: wb.tool === 'eraser' ? '#0a0f1a' : wb.color, size: wb.size });
      [lastX, lastY] = [e.offsetX, e.offsetY];
    }
  });
  canvas.addEventListener('mouseup', (e) => {
    if (!wb.drawing) return;
    wb.drawing = false;
    if (wb.tool === 'rect') {
      ctx.strokeStyle = wb.color; ctx.lineWidth = wb.size;
      ctx.strokeRect(lastX, lastY, e.offsetX - lastX, e.offsetY - lastY);
    } else if (wb.tool === 'circle') {
      const r = Math.hypot(e.offsetX - lastX, e.offsetY - lastY);
      ctx.beginPath(); ctx.arc(lastX, lastY, r, 0, Math.PI * 2);
      ctx.strokeStyle = wb.color; ctx.lineWidth = wb.size; ctx.stroke();
    } else if (wb.tool === 'line') {
      ctx.beginPath(); ctx.moveTo(lastX, lastY); ctx.lineTo(e.offsetX, e.offsetY);
      ctx.strokeStyle = wb.color; ctx.lineWidth = wb.size; ctx.stroke();
    }
  });
}

function setTool(t) {
  APP.whiteboard.tool = t;
  document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`tool-${t}`)?.classList.add('active');
}
function setColor(c) { APP.whiteboard.color = c; }
function setBrushSize(s) { APP.whiteboard.size = parseInt(s); }
function clearCanvas() {
  const c = document.getElementById('whiteboard-canvas');
  c.getContext('2d').clearRect(0, 0, c.width, c.height);
}
function saveCanvas() {
  const c = document.getElementById('whiteboard-canvas');
  const a = document.createElement('a'); a.download = 'whiteboard.png'; a.href = c.toDataURL(); a.click();
}
function emitDraw(data) {
  if (APP.socket && APP.currentTeam) APP.socket.emit('whiteboard_draw', { team_id: getTeamId(), ...data });
}
function remoteWhiteboardDraw(data) {
  const c = document.getElementById('whiteboard-canvas');
  if (!c) return;
  const ctx = c.getContext('2d');
  if (data.type === 'line') {
    ctx.beginPath(); ctx.moveTo(data.x1, data.y1); ctx.lineTo(data.x2, data.y2);
    ctx.strokeStyle = data.color; ctx.lineWidth = data.size; ctx.lineCap = 'round'; ctx.stroke();
  } else if (data.type === 'text') {
    ctx.fillStyle = data.color; ctx.font = '16px DM Sans'; ctx.fillText(data.text, data.x, data.y);
  }
}

// ── Editor ────────────────────────────────────────────────
function initEditor() {
  if (APP.editor) return;
  require(['vs/editor/editor.main'], () => {
    APP.editor = monaco.editor.create(document.getElementById('monaco-container'), {
      value: '// Welcome to HackForge Code Editor\n// Start coding...\n\nconsole.log("Hello, HackForge!");',
      language: 'javascript',
      theme: 'vs-dark',
      fontSize: 14,
      fontFamily: "'Space Mono', monospace",
      minimap: { enabled: true },
      automaticLayout: true,
      wordWrap: 'on',
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      renderWhitespace: 'selection',
    });
    // Collaborative: broadcast changes via socket
    APP.editor.onDidChangeModelContent(() => {
      if (APP.socket && APP.currentTeam) {
        APP.socket.emit('editor_change', { team_id: getTeamId(), content: APP.editor.getValue() });
      }
    });
  });
}

function setEditorLanguage() {
  if (!APP.editor) return;
  const lang = document.getElementById('editor-lang').value;
  monaco.editor.setModelLanguage(APP.editor.getModel(), lang);
}
function formatCode() {
  if (APP.editor) APP.editor.getAction('editor.action.formatDocument').run();
}
async function runCode() {
  if (!APP.editor) return;
  const code = APP.editor.getValue();
  const lang = document.getElementById('editor-lang').value;
  document.getElementById('output-content').textContent = 'Running...';
  const res = await API.post('/ai/run-code', { code, language: lang, team_id: getTeamId() });
  if (res.ok) document.getElementById('output-content').textContent = res.data.data?.output || 'No output';
  else document.getElementById('output-content').textContent = res.data.error || 'Execution failed';
}
function clearOutput() { document.getElementById('output-content').textContent = 'Ready to run...'; }

// ── Terminal ──────────────────────────────────────────────
const termHistory = [];
let termIdx = -1;
function initTerminal() {
  const out = document.getElementById('terminal-output');
  if (!out.hasChildNodes()) {
    out.innerHTML = `<div style="color:var(--neon-cyan)">HackForge Terminal v1.0</div>
    <div style="color:var(--text-muted);font-size:11px">Type code and press Enter to execute.</div>\n`;
  }
}
async function termKeydown(e) {
  const input = document.getElementById('terminal-input');
  if (e.key === 'Enter') {
    const cmd = input.value.trim();
    if (!cmd) return;
    termHistory.unshift(cmd); termIdx = -1;
    printTerm(`❯ ${cmd}`, 'var(--text-primary)');
    input.value = '';
    const lang = document.getElementById('term-lang').value;
    const res = await API.post('/ai/run-code', { code: cmd, language: lang, team_id: getTeamId() });
    printTerm(res.ok ? (res.data.data?.output || 'OK') : (res.data.error || 'Error'), res.ok ? 'var(--neon-green)' : '#ef4444');
  } else if (e.key === 'ArrowUp') { termIdx = Math.min(termIdx+1, termHistory.length-1); input.value = termHistory[termIdx] || ''; }
  else if (e.key === 'ArrowDown') { termIdx = Math.max(termIdx-1, -1); input.value = termIdx >= 0 ? termHistory[termIdx] : ''; }
}
function printTerm(text, color='var(--neon-green)') {
  const out = document.getElementById('terminal-output');
  const div = document.createElement('div');
  div.style.color = color;
  div.textContent = text;
  out.appendChild(div);
  out.scrollTop = out.scrollHeight;
}
function clearTerminal() { document.getElementById('terminal-output').innerHTML = ''; initTerminal(); }

// ── Presence ──────────────────────────────────────────────
function updatePresence(data) {
  // Could update member presence indicators
}

// ── Modals ────────────────────────────────────────────────
function openModal(title, body) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = body;
  document.getElementById('modal').classList.remove('hidden');
  document.getElementById('modal-overlay').classList.remove('hidden');
}
function closeModal() {
  document.getElementById('modal').classList.add('hidden');
  document.getElementById('upload-modal').classList.add('hidden');
  document.getElementById('modal-overlay').classList.add('hidden');
}

// ── Create Modals ─────────────────────────────────────────
function showCreateTeamModal() {
  openModal('Create Team', `
    <div class="form-group"><label>Team Name</label><input type="text" id="new-team-name" class="neon-input" placeholder="Awesome Hackers" /></div>
    <div class="form-group"><label>Description</label><textarea id="new-team-desc" class="neon-input" rows="3" placeholder="What will you build?"></textarea></div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitCreateTeam()">Create Team</button>
    </div>
  `);
}
async function submitCreateTeam() {
  const name = document.getElementById('new-team-name').value.trim();
  const desc = document.getElementById('new-team-desc').value.trim();
  if (!name) return toast('Team name required', 'error');
  const res = await API.post('/teams', { name, description: desc });
  if (res.ok) {
    closeModal();
    const tRes = await API.get('/auth/me');
    if (tRes.ok) { APP.user = tRes.data.data.user; APP.teams = APP.user.memberships || []; }
    const newTeam = APP.teams.find(m => m.teams?.name === name);
    if (newTeam) setCurrentTeam(newTeam);
    toast(`Team "${name}" created!`, 'success');
    loadDashboard();
  } else toast(res.data.error || 'Failed to create team', 'error');
}

function showCreateProjectModal() {
  const teamId = getTeamId();
  openModal('Create Project', `
    <div class="form-group"><label>Project Name</label><input type="text" id="new-proj-name" class="neon-input" placeholder="My Awesome Project" /></div>
    <div class="form-group"><label>Description</label><textarea id="new-proj-desc" class="neon-input" rows="3" placeholder="What will this project do?"></textarea></div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitCreateProject('${teamId}')">Create Project</button>
    </div>
  `);
}
async function submitCreateProject(teamId) {
  const name = document.getElementById('new-proj-name').value.trim();
  const desc = document.getElementById('new-proj-desc').value.trim();
  if (!name) return;
  const res = await API.post(`/teams/${teamId}/projects`, { name, description: desc });
  if (res.ok) { closeModal(); loadDashboard(); toast('Project created!', 'success'); }
  else toast(res.data.error || 'Failed', 'error');
}

function showCreateModal() {
  openModal('Quick Create', `
    <div style="display:flex;flex-direction:column;gap:8px">
      <button class="btn-secondary full-width" style="justify-content:flex-start;gap:10px" onclick="closeModal();showCreateTeamModal()"><i class="fas fa-users"></i> New Team</button>
      <button class="btn-secondary full-width" style="justify-content:flex-start;gap:10px" onclick="closeModal();showCreateProjectModal()"><i class="fas fa-rocket"></i> New Project</button>
      <button class="btn-secondary full-width" style="justify-content:flex-start;gap:10px" onclick="closeModal();showCreateTaskModal()"><i class="fas fa-tasks"></i> New Task</button>
      <button class="btn-secondary full-width" style="justify-content:flex-start;gap:10px" onclick="closeModal();showUploadModal()"><i class="fas fa-upload"></i> Upload Files</button>
    </div>
  `);
}

// ── Command Palette ───────────────────────────────────────
const COMMANDS = [
  { group: 'Navigate', icon: 'fas fa-th-large', label: 'Dashboard', action: () => navigate('dashboard') },
  { group: 'Navigate', icon: 'fas fa-tasks', label: 'Tasks', action: () => navigate('tasks') },
  { group: 'Navigate', icon: 'fas fa-code', label: 'Code Editor', action: () => navigate('editor') },
  { group: 'Navigate', icon: 'fas fa-terminal', label: 'Terminal', action: () => navigate('terminal') },
  { group: 'Navigate', icon: 'fas fa-comments', label: 'Chat', action: () => navigate('chat') },
  { group: 'Navigate', icon: 'fas fa-folder', label: 'Files', action: () => navigate('files') },
  { group: 'Navigate', icon: 'fas fa-brain', label: 'AI Copilot', action: () => navigate('ai') },
  { group: 'Navigate', icon: 'fas fa-chart-bar', label: 'Analytics', action: () => navigate('analytics') },
  { group: 'Navigate', icon: 'fas fa-cog', label: 'Settings', action: () => navigate('settings') },
  { group: 'Actions', icon: 'fas fa-plus', label: 'Create Task', action: () => { hideCommandPalette(); showCreateTaskModal(); } },
  { group: 'Actions', icon: 'fas fa-upload', label: 'Upload Files', action: () => { hideCommandPalette(); showUploadModal(); } },
  { group: 'Actions', icon: 'fas fa-user-plus', label: 'Invite Member', action: () => { hideCommandPalette(); showInviteModal(); } },
  { group: 'Actions', icon: 'fas fa-rocket', label: 'Deploy Project', action: () => { hideCommandPalette(); showDeployModal(); } },
  { group: 'Actions', icon: 'fas fa-sign-out-alt', label: 'Logout', action: authLogout },
];

function showCommandPalette() {
  document.getElementById('cmd-palette').classList.remove('hidden');
  document.getElementById('cmd-input').value = '';
  document.getElementById('cmd-input').focus();
  filterCommands('');
}
function hideCommandPalette() { document.getElementById('cmd-palette').classList.add('hidden'); }
function filterCommands(query) {
  const q = query.toLowerCase();
  const results = COMMANDS.filter(c => c.label.toLowerCase().includes(q));
  const el = document.getElementById('cmd-results');
  el.innerHTML = '';
  let lastGroup = '';
  results.forEach((c, i) => {
    if (c.group !== lastGroup) {
      const g = document.createElement('div'); g.className = 'cmd-group-label'; g.textContent = c.group;
      el.appendChild(g); lastGroup = c.group;
    }
    const item = document.createElement('div');
    item.className = `cmd-item${i === APP.cmdSelectedIndex ? ' selected' : ''}`;
    item.innerHTML = `<i class="${c.icon}"></i><span>${c.label}</span>`;
    item.onclick = () => { hideCommandPalette(); c.action(); };
    el.appendChild(item);
  });
}
function cmdKeydown(e) {
  const items = document.querySelectorAll('.cmd-item');
  if (e.key === 'ArrowDown') { APP.cmdSelectedIndex = Math.min(APP.cmdSelectedIndex+1, items.length-1); updateCmdSelection(items); }
  else if (e.key === 'ArrowUp') { APP.cmdSelectedIndex = Math.max(APP.cmdSelectedIndex-1, 0); updateCmdSelection(items); }
  else if (e.key === 'Enter') { items[APP.cmdSelectedIndex]?.click(); }
}
function updateCmdSelection(items) {
  items.forEach((el, i) => el.classList.toggle('selected', i === APP.cmdSelectedIndex));
  items[APP.cmdSelectedIndex]?.scrollIntoView({ block: 'nearest' });
}

// ── Toast ─────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };
  const div = document.createElement('div');
  div.className = `toast ${type}`;
  div.innerHTML = `
    <i class="fas ${icons[type]} toast-icon"></i>
    <span class="toast-msg">${escHtml(msg)}</span>
    <button class="toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
  `;
  document.getElementById('toast-container').appendChild(div);
  setTimeout(() => div.remove(), 4000);
}

// ── Profile Modal ─────────────────────────────────────────
function showProfileModal() { navigate('settings'); }

// ── Sidebar Toggle ────────────────────────────────────────
function toggleSidebar() { document.getElementById('sidebar').classList.toggle('collapsed'); }

// ── Helpers ───────────────────────────────────────────────
function getTeamId() {
  if (!APP.currentTeam) return null;
  return APP.currentTeam.team_id || APP.currentTeam.teams?.id || APP.currentTeam.id;
}
function selectProject(id, name) { APP.currentProject = { id, name }; navigate('tasks'); }
function userAvatar(user) {
  if (!user) return 'https://api.dicebear.com/7.x/identicon/svg?seed=default';
  if (user.avatar_url) return user.avatar_url;
  return `https://api.dicebear.com/7.x/identicon/svg?seed=${user.username || user.id || 'user'}`;
}
function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function timeAgo(iso) {
  if (!iso) return '';
  const s = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (s < 60) return 'just now';
  const m = Math.floor(s/60); if (m < 60) return `${m}m ago`;
  const h = Math.floor(m/60); if (h < 24) return `${h}h ago`;
  const d = Math.floor(h/24); return `${d}d ago`;
}
function formatDate(iso) { if (!iso) return ''; return new Date(iso).toLocaleDateString(); }
function formatBytes(b) {
  if (!b) return '0 B';
  const k = 1024; const s = ['B','KB','MB','GB'];
  const i = Math.floor(Math.log(b)/Math.log(k));
  return (b/Math.pow(k,i)).toFixed(1)+' '+s[i];
}
function searchFiles(q) {
  document.querySelectorAll('.file-card').forEach(c => {
    const name = c.querySelector('.file-name')?.textContent.toLowerCase() || '';
    c.style.display = name.includes(q.toLowerCase()) ? '' : 'none';
  });
}
function navigateFiles(folderId) { /* folder navigation */ }
function showCreateFolderModal() {
  openModal('New Folder', `
    <div class="form-group"><label>Folder Name</label><input type="text" id="folder-name" class="neon-input" placeholder="My Folder" /></div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="createFolder()">Create</button>
    </div>
  `);
}
async function createFolder() {
  const name = document.getElementById('folder-name').value.trim();
  if (!name) return;
  await API.post('/storage/folders', { name, team_id: getTeamId() });
  closeModal(); loadFiles(); toast('Folder created!', 'success');
}
function openFile(fileId) { downloadFile(fileId); }
function showDMModal() { toast('DMs coming soon!', 'info'); }
function showCreateChannelModal() {
  const teamId = getTeamId();
  openModal('Create Channel', `
    <div class="form-group"><label>Channel Name</label><input type="text" id="chan-name" class="neon-input" placeholder="e.g. design-team" /></div>
    <div class="modal-footer">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="createChannel('${teamId}')">Create</button>
    </div>
  `);
}
async function createChannel(teamId) {
  const name = document.getElementById('chan-name').value.trim().replace(/\s+/g, '-').toLowerCase();
  if (!name) return;
  const res = await API.post('/chat/rooms', { name, team_id: teamId, type: 'channel' });
  if (res.ok) { closeModal(); loadChat(); toast(`#${name} created!`, 'success'); }
  else toast(res.data.error || 'Failed', 'error');
}
function toggleEmojiPicker() { toast('Emoji picker coming soon!', 'info'); }
function triggerFileUpload() { showUploadModal(); }
function editWikiPage(id) { toast('Wiki editor coming soon!', 'info'); }