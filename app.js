const app = document.getElementById('app');
const state = {
  screen: 'home',
  selectedNote: null,
  unlocked: false,
  section: 'dashboard',
};

const notes = [
  { id: 1, title: 'Lemon Herb Chicken', cat: 'Recipes', body: 'Marinate with olive oil, lemon zest, garlic, thyme. Roast 35 mins.', date: '2026-05-11' },
  { id: 2, title: 'Spring Reading List', cat: 'Reading', body: 'Finish “Invisible Cities”, start “The Overstory”.', date: '2026-05-09' },
  { id: 3, title: 'Weekend Garden Plan', cat: 'Garden', body: 'Repot basil and mint. Prep tomato stakes.', date: '2026-05-06' },
  { id: 4, title: 'Bills + reminders', cat: 'Reminders', body: 'Renew car registration and schedule annual checkup.', date: '2026-05-05' },
];

const files = [
  ['Legacy Letter Packet', 'enc_9d3f6ae112', 'Letters', 'High', 'Protected', '2026-05-03'],
  ['Medical History Archive', 'enc_2a7be019d8', 'Documents', 'Critical', 'Protected', '2026-04-28'],
  ['Case Notes 2017', 'enc_f7ce4209b4', 'Case Files', 'High', 'Review', '2026-04-21'],
];

function setScreen(s){ state.screen = s; render(); }
function setSection(s){ state.section = s; render(); }

function renderHome(){
  return `<div class="container">
    <header><h1>Stone Notes</h1><div class="hidden-dot" title="footer mark" onclick="setScreen('trigger')"></div></header>
    <p class="small">A simple space for recipes, reminders, and reading notes.</p>
    <div class="grid">
      ${notes.map(n => `<div class="card"><div class="note-title">${n.title}</div><div class="small">${n.cat} · ${n.date}</div><p>${n.body.slice(0,65)}...</p><button class="secondary" onclick="openNote(${n.id})">Open note</button></div>`).join('')}
    </div>
  </div>`;
}

function renderNote(){
  const n = notes.find(x => x.id === state.selectedNote);
  return `<div class="container"><div class="card"><h2>${n.title}</h2><p class="small">${n.cat} · ${n.date}</p><p>${n.body}</p><button onclick="setScreen('home')">Back</button></div></div>`;
}

function renderTrigger(){
  return `<div class="container"><div class="card"><h2>Continue</h2><p class="small">Enter access phrase.</p><input id="phrase" placeholder="Phrase" /><button onclick="checkPhrase()">Continue</button> <button class="secondary" onclick="setScreen('home')">Cancel</button><p id="pmsg" class="small"></p></div></div>`;
}

function renderVaultLogin(){
  return `<div class="container"><div class="card"><h2>Vault Login</h2>
  <div class="callout">Prototype only. Production security requires audited cryptographic implementation. Master passphrase must never leave the device.</div>
  <label>Master passphrase</label><input id="pass" type="password" placeholder="Enter master passphrase"/><button onclick="loginVault()">Unlock Vault</button><p id="lmsg" class="small"></p></div></div>`;
}

function renderVault(){
  const section = state.section;
  return `<div class="container"><header><h1>Project Bedrock Vault</h1><button onclick="lockVault()">Lock</button></header>
  <div class="nav">${['dashboard','files','detail','upload','security','settings'].map(s=>`<button onclick="setSection('${s}')">${s[0].toUpperCase()+s.slice(1)}</button>`).join('')}</div>
  ${section === 'dashboard' ? `<div class="grid">${['Documents','Letters','Case Files','Personal Writing','Backups','Security','Settings'].map(x=>`<div class='card'><h3>${x}</h3><p class='small'>Private vault section.</p></div>`).join('')}</div><div class='card'><h3>Recent Activity</h3><p class='small mono'>2026-05-13: integrity check passed · 2026-05-12: encrypted upload completed.</p></div>` : ''}
  ${section === 'files' ? `<div class='card'><h3>Encrypted File List</h3><table class='table'><thead><tr><th>Display Name</th><th>Encrypted ID</th><th>Category</th><th>Sensitivity</th><th>Status</th><th>Date Added</th></tr></thead><tbody>${files.map(f=>`<tr><td>${f[0]}</td><td class='mono'>${f[1]}</td><td>${f[2]}</td><td>${f[3]}</td><td><span class='badge ${f[4]==='Protected'?'ok':'warn'}'>${f[4]}</span></td><td>${f[5]}</td></tr>`).join('')}</tbody></table></div>` : ''}
  ${section === 'detail' ? `<div class='card'><h3>File Detail</h3><p><b>Display name:</b> Medical History Archive</p><p><b>Encrypted filename:</b> <span class='mono'>f_ae903c76bd.bin</span></p><p><b>Category:</b> Documents</p><p><b>Sensitivity:</b> Critical</p><p><b>Notes:</b> Family medical scans and records, encrypted client-side.</p><p><b>Recovery contact:</b> Trusted contact documented offline.</p><h4>Audit Log</h4><ul><li>2026-05-10: decrypted locally</li><li>2026-05-10: checksum verified</li><li>2026-05-09: encrypted upload</li></ul></div>` : ''}
  ${section === 'upload' ? `<div class='card'><h3>Upload Simulation</h3><ol><li>Select file</li><li>Encrypt locally (AES-256-GCM)</li><li>Strip metadata</li><li>Upload encrypted blob</li><li>Verify integrity</li><li>Store encrypted record</li></ol><input type='file'/><button onclick="alert('Simulated: encrypted blob uploaded; plaintext never sent.')">Run simulation</button></div>` : ''}
  ${section === 'security' ? `<div class='card'><h3>Security Checklist</h3><ul class='checklist'><li>AES-256-GCM encryption</li><li>Client-side encryption only</li><li>Master passphrase never sent to server</li><li>Unique nonce per file</li><li>Encrypted metadata</li><li>HTTPS required</li><li>Short session expiry</li><li>Auto-lock after inactivity</li></ul></div>` : ''}
  ${section === 'settings' ? `<div class='card'><h3>Settings</h3><label>Auto-lock timeout</label><select><option>5 minutes</option><option selected>10 minutes</option><option>15 minutes</option></select><label>Trusted contact notes</label><textarea>Keep sealed instructions with attorney and sibling.</textarea><label>Recovery instructions</label><textarea>Offline recovery packet in fireproof safe.</textarea><label>Backup reminders</label><select><option>Weekly</option><option selected>Monthly</option></select><label>Emergency access planning</label><textarea>Two-stage disclosure process documented offline.</textarea></div>` : ''}
  </div>`;
}

function render(){
  if (state.screen === 'home') app.innerHTML = renderHome();
  if (state.screen === 'note') app.innerHTML = renderNote();
  if (state.screen === 'trigger') app.innerHTML = renderTrigger();
  if (state.screen === 'login') app.innerHTML = renderVaultLogin();
  if (state.screen === 'vault') app.innerHTML = renderVault();
}

window.openNote = (id) => { state.selectedNote = id; setScreen('note'); };
window.checkPhrase = () => {
  const phrase = document.getElementById('phrase').value.trim();
  if (phrase.toLowerCase() === 'bedrock entry') setScreen('login');
  else { document.getElementById('pmsg').textContent = 'Unable to continue.'; setTimeout(()=>setScreen('home'), 900); }
};
window.loginVault = () => {
  const pass = document.getElementById('pass').value;
  if (pass.length >= 8) setScreen('vault');
  else document.getElementById('lmsg').textContent = 'Invalid credentials.';
};
window.lockVault = () => { state.section = 'dashboard'; setScreen('home'); };
window.setScreen = setScreen;
window.setSection = setSection;
render();
