// ── State ─────────────────────────────────────────────────────────────────

let activeConversationId = null;
let activeMode = 'search'; // 'search' | 'summarize'

function toggleMode() {
  activeMode = activeMode === 'search' ? 'summarize' : 'search';
  const btn = document.getElementById('modeBtn');
  btn.textContent = activeMode === 'search' ? 'Search' : 'Summarize';
  btn.classList.toggle('mode-summarize', activeMode === 'summarize');
}


// ── Upload ────────────────────────────────────────────────────────────────

const fileInput = document.getElementById('fileInput');

document.getElementById('uploadBtn').addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleUpload(fileInput.files[0]);
  fileInput.value = '';
});

async function handleUpload(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showError('Only PDF files are supported.');
    return;
  }

  setUploadStatus(`Uploading…`);
  clearError();

  const formData = new FormData();
  formData.append('file', file);
  if (activeConversationId !== null) {
    formData.append('conversation_id', activeConversationId);
  }

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed.');
    }
    const data = await res.json();

    // If a new conversation was auto-created, activate it
    if (activeConversationId === null && data.conversation_id) {
      activeConversationId = data.conversation_id;
      await loadConversations();
    }

    setUploadStatus(`Indexed ${data.chunks} chunks`);
    setTimeout(() => setUploadStatus(''), 3000);
    await loadDocuments();
  } catch (e) {
    setUploadStatus('');
    showError(e.message);
  }
}

function setUploadStatus(msg) {
  document.getElementById('uploadStatus').textContent = msg;
}


// ── Documents ─────────────────────────────────────────────────────────────

async function loadDocuments() {
  try {
    const url = activeConversationId !== null
      ? `/documents?conversation_id=${activeConversationId}`
      : '/documents';
    const res = await fetch(url);
    const data = await res.json();
    renderDocuments(data.documents);
  } catch (_) {}
}

function renderDocuments(docs) {
  const container = document.getElementById('docList');
  container.innerHTML = '';
  docs.forEach(name => {
    const item = document.createElement('div');
    item.className = 'doc-item';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'doc-name';
    nameSpan.textContent = name;
    nameSpan.title = name;

    const btn = document.createElement('button');
    btn.className = 'doc-remove';
    btn.textContent = '×';
    btn.title = 'Remove document';
    btn.onclick = () => removeDocument(name);

    item.appendChild(nameSpan);
    item.appendChild(btn);
    container.appendChild(item);
  });
}

async function removeDocument(name) {
  try {
    const url = activeConversationId !== null
      ? `/documents/${encodeURIComponent(name)}?conversation_id=${activeConversationId}`
      : `/documents/${encodeURIComponent(name)}`;
    await fetch(url, { method: 'DELETE' });
    await loadDocuments();
  } catch (_) {}
}


// ── Conversations ─────────────────────────────────────────────────────────

async function loadConversations() {
  try {
    const res = await fetch('/conversations');
    const data = await res.json();
    renderConversations(data.conversations);
  } catch (_) {}
}

function renderConversations(convs) {
  const container = document.getElementById('convList');
  container.innerHTML = '';

  if (convs.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'conv-empty';
    empty.textContent = 'No chats yet';
    container.appendChild(empty);
    return;
  }

  convs.forEach(conv => {
    const item = document.createElement('div');
    item.className = 'conv-item' + (conv.id === activeConversationId ? ' active' : '');
    item.dataset.id = conv.id;

    const title = document.createElement('span');
    title.className = 'conv-title';
    title.textContent = conv.title;
    title.title = conv.title;
    title.onclick = () => loadConversation(conv.id);

    const btn = document.createElement('button');
    btn.className = 'conv-remove';
    btn.textContent = '×';
    btn.title = 'Delete chat';
    btn.onclick = e => { e.stopPropagation(); deleteConversation(conv.id); };

    item.appendChild(title);
    item.appendChild(btn);
    container.appendChild(item);
  });
}

async function loadConversation(id) {
  try {
    const res = await fetch(`/conversations/${id}/messages`);
    if (!res.ok) return;
    const data = await res.json();

    activeConversationId = id;

    // Clear chat
    const messages = document.getElementById('messages');
    messages.innerHTML = '';

    if (data.messages.length === 0) {
      messages.innerHTML = '<div class="empty-state" id="emptyState"><div class="empty-icon">💬</div><p>Upload a PDF and start asking questions</p></div>';
    } else {
      data.messages.forEach(msg => {
        const wrapper = addMessage(msg.role, msg.content);
        if (msg.role === 'assistant' && msg.sources && msg.sources.length > 0) {
          renderSources(msg.sources, wrapper);
        }
      });
    }

    renderConversations(await fetchConversations());
    scrollToBottom();
  } catch (_) {}
}

async function fetchConversations() {
  const res = await fetch('/conversations');
  const data = await res.json();
  return data.conversations;
}

async function deleteConversation(id) {
  try {
    await fetch(`/conversations/${id}`, { method: 'DELETE' });
    if (activeConversationId === id) {
      newConversation();
    } else {
      await loadConversations();
    }
  } catch (_) {}
}

function newConversation() {
  activeConversationId = null;

  const messages = document.getElementById('messages');
  messages.innerHTML = '<div class="empty-state" id="emptyState"><div class="empty-icon">💬</div><p>Upload a PDF and start asking questions</p></div>';

  loadConversations();
  loadDocuments();
  clearError();
}


// ── Chat ──────────────────────────────────────────────────────────────────

async function askQuestion() {
  const textarea = document.getElementById('question');
  const question = textarea.value.trim();
  if (!question) return;

  clearError();

  addMessage('user', question);
  textarea.value = '';
  autoResize(textarea);

  const assistantBubble = addMessage('assistant', '');
  const textEl  = assistantBubble.querySelector('.message-bubble');
  const btn     = document.getElementById('askBtn');

  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div>';

  // Smooth typewriter: drain a queue at ~30 chars/frame via rAF
  let textQueue = '';
  let rafId = null;

  function drainQueue() {
    if (textQueue.length === 0) { rafId = null; return; }
    const chunk = textQueue.slice(0, 6);
    textQueue   = textQueue.slice(6);
    textEl.textContent += chunk;
    scrollToBottom();
    rafId = requestAnimationFrame(drainQueue);
  }

  function enqueue(text) {
    textQueue += text;
    if (!rafId) rafId = requestAnimationFrame(drainQueue);
  }

  async function flushQueue() {
    return new Promise(resolve => {
      function flush() {
        if (textQueue.length === 0) { rafId = null; resolve(); return; }
        const chunk = textQueue.slice(0, 6);
        textQueue   = textQueue.slice(6);
        textEl.textContent += chunk;
        scrollToBottom();
        rafId = requestAnimationFrame(flush);
      }
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(flush);
    });
  }

  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, conversation_id: activeConversationId, mode: activeMode }),
    });

    if (!res.ok) throw new Error('Request failed.');

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();

      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        const event = JSON.parse(part.slice(6));

        if (event.type === 'conversation_id') {
          if (activeConversationId === null) {
            activeConversationId = event.id;
            await loadConversations();
          }

        } else if (event.type === 'chunk') {
          enqueue(event.text);

        } else if (event.type === 'done') {
          await flushQueue();
          renderSources(event.sources, assistantBubble);
          scrollToBottom();

        } else if (event.type === 'error') {
          await flushQueue();
          textEl.textContent = event.message;
          scrollToBottom();
        }
      }
    }
  } catch (e) {
    showError(e.message);
    assistantBubble.remove();
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round">
      <line x1="12" y1="19" x2="12" y2="5"/>
      <polyline points="5 12 12 5 19 12"/>
    </svg>`;
  }
}

function addMessage(role, text) {
  const emptyState = document.getElementById('emptyState');
  if (emptyState) emptyState.remove();

  const messages = document.getElementById('messages');

  const wrapper = document.createElement('div');
  wrapper.className = `message message-${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  messages.appendChild(wrapper);
  scrollToBottom();

  return wrapper;
}

function renderSources(sources, messageEl) {
  if (!sources || sources.length === 0) return;

  const details = document.createElement('details');
  details.className = 'message-sources';

  const summary = document.createElement('summary');
  summary.className = 'sources-label';
  summary.textContent = `Sources (${sources.length})`;
  details.appendChild(summary);

  sources.forEach(src => {
    const div = document.createElement('div');
    div.className = 'source-item';
    div.textContent = src;
    details.appendChild(div);
  });

  messageEl.appendChild(details);
}

function scrollToBottom() {
  const messages = document.getElementById('messages');
  messages.scrollTop = messages.scrollHeight;
}


// ── Input auto-resize ──────────────────────────────────────────────────────

const textarea = document.getElementById('question');

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

textarea.addEventListener('input', () => autoResize(textarea));

textarea.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    askQuestion();
  }
});


// ── Error helpers ─────────────────────────────────────────────────────────

function showError(msg) {
  const el = document.getElementById('error');
  el.textContent = msg;
  el.classList.add('visible');
}

function clearError() {
  const el = document.getElementById('error');
  el.textContent = '';
  el.classList.remove('visible');
}


// ── Init ──────────────────────────────────────────────────────────────────

loadDocuments();
loadConversations();


// ── GSAP scroll animations ────────────────────────────────────────────────

gsap.registerPlugin(ScrollTrigger);

// ── Feature card carousel ─────────────────────────────────────────────────

const carouselTrack = document.querySelector('.features-track');
const carouselCards = Array.from(document.querySelectorAll('.feature-card'));
const CAROUSEL_GAP  = 20; // px — matches gap: 1.25rem
const CARDS_VISIBLE = 3.2; // how many cards show at once (rest peek to the right)
const TOTAL_STEPS   = carouselCards.length - 2; // last step shows final 2 cards
let carouselStep    = 0;

function initCarousel() {
  // Visible width = from carousel left edge to viewport right edge
  const carouselEl  = document.querySelector('.features-carousel');
  const carouselLeft = carouselEl.getBoundingClientRect().left;
  const visibleWidth = window.innerWidth - carouselLeft;
  const cardWidth    = (visibleWidth - CAROUSEL_GAP * (CARDS_VISIBLE - 1)) / CARDS_VISIBLE;
  carouselCards.forEach(card => { card.style.width = cardWidth + 'px'; });
  goToStep(carouselStep, false);
}

function updateCarouselButtons() {
  document.getElementById('carouselPrev').disabled = carouselStep === 0;
  document.getElementById('carouselNext').disabled = carouselStep >= TOTAL_STEPS;
}

function goToStep(step, animate = true) {
  if (step < 0 || step > TOTAL_STEPS) return;
  const cardWidth = carouselCards[0].offsetWidth;
  const offset    = step * (cardWidth + CAROUSEL_GAP);

  if (animate) {
    gsap.to(carouselTrack, { x: -offset, duration: 0.55, ease: 'power2.inOut' });
  } else {
    gsap.set(carouselTrack, { x: -offset });
  }

  carouselStep = step;
  updateCarouselButtons();
}

function carouselPrev() { goToStep(carouselStep - 1); }
function carouselNext() { goToStep(carouselStep + 1); }

window.addEventListener('load', initCarousel);
window.addEventListener('resize', initCarousel);

// Section fade-in on scroll
gsap.from('.features .section-title, .features .section-subtitle', {
  scrollTrigger: { trigger: '.features', start: 'top 80%' },
  y: 24, opacity: 0, duration: 0.7, stagger: 0.15, ease: 'power2.out',
});

gsap.from('.features-carousel', {
  scrollTrigger: { trigger: '.features-carousel', start: 'top 82%' },
  y: 30, opacity: 0, duration: 0.7, ease: 'power2.out',
});

// How it works steps
window.addEventListener('load', () => {
  gsap.utils.toArray('.step').forEach((step, i) => {
    gsap.from(step, {
      scrollTrigger: {
        trigger: step,
        start: 'top 65%',
        toggleActions: 'play none none reverse',
      },
      x: -30, opacity: 0, duration: 0.6, delay: i * 0.08, ease: 'power2.out',
    });
  });

  gsap.from('.tech-stack', {
    scrollTrigger: { trigger: '.tech-stack', start: 'top 92%' },
    y: 20, opacity: 0, duration: 0.6, ease: 'power2.out',
  });
});
