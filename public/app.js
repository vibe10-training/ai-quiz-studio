const STORAGE_KEY = "ai_quiz_studio_gallery_v1";

const state = {
  activeTab: "generator",
  currentQuiz: null,
  userAnswers: {},
  isSubmitted: false,
  previewAnswers: false,
  gallery: [],
};

const DIFFICULTY_LABEL = {
  easy: "쉬움",
  medium: "보통",
  hard: "어려움",
};

const TYPE_LABEL = {
  multiple_choice: "객관식",
  short_answer: "주관식",
};

// ---------- Storage Helpers ----------
function loadGallery() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    state.gallery = Array.isArray(parsed) ? parsed : [];
  } catch {
    state.gallery = [];
  }
  updateGalleryBadge();
}

function persistGallery() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.gallery));
  updateGalleryBadge();
}

function updateGalleryBadge() {
  const badge = document.getElementById("gallery-count-badge");
  if (badge) badge.textContent = String(state.gallery.length);
}

// ---------- UI Helpers ----------
let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 2800);
}

function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  document.getElementById("view-generator").classList.toggle("hidden", tabName !== "generator");
  document.getElementById("view-gallery").classList.toggle("hidden", tabName !== "gallery");

  if (tabName === "gallery") {
    renderGallery();
  }
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeAnswerText(val) {
  return String(val ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

// ---------- Health Check ----------
async function checkServerHealth() {
  const pill = document.getElementById("ai-status-pill");
  const text = document.getElementById("ai-status-text");
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();
    if (data.ai_configured) {
      pill.className = "status-pill ok";
      text.textContent = `AI 연결됨 (${data.model || "ready"})`;
    } else {
      pill.className = "status-pill warn";
      text.textContent = "env_local 키 설정 필요";
    }
  } catch {
    pill.className = "status-pill warn";
    text.textContent = "서버 연결 확인 필요";
  }
}

// ---------- Quiz Generation ----------
async function handleGenerateSubmit(event) {
  event.preventDefault();
  const errorBox = document.getElementById("form-error");
  errorBox.classList.add("hidden");

  const subject = document.getElementById("input-subject").value.trim();
  const unit = document.getElementById("input-unit").value.trim();
  const questionType = document.querySelector('input[name="question_type"]:checked').value;
  const count = Number(document.getElementById("input-count").value);
  const difficulty = document.getElementById("input-difficulty").value;

  if (!subject || !unit) {
    errorBox.textContent = "과목명과 단원명을 모두 입력해 주세요.";
    errorBox.classList.remove("hidden");
    return;
  }

  const btn = document.getElementById("btn-generate");
  const loadingBox = document.getElementById("loading-box");
  const workspace = document.getElementById("quiz-workspace");

  btn.disabled = true;
  loadingBox.classList.remove("hidden");
  workspace.classList.add("hidden");

  try {
    const res = await fetch("/api/quiz/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject,
        unit,
        question_type: questionType,
        count,
        difficulty,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "퀴즈 생성 중 오류가 발생했습니다.");
    }

    loadQuizIntoWorkspace(data);
    showToast("퀴즈와 해설이 생성되었습니다!");
  } catch (err) {
    errorBox.textContent = err.message || "네트워크 오류가 발생했습니다.";
    errorBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    loadingBox.classList.add("hidden");
  }
}

function loadQuizIntoWorkspace(quizData, options = { previewAnswers: false }) {
  state.currentQuiz = quizData;
  state.userAnswers = {};
  state.isSubmitted = false;
  state.previewAnswers = Boolean(options.previewAnswers);

  document.getElementById("toggle-preview-answers").checked = state.previewAnswers;
  document.getElementById("quiz-workspace").classList.remove("hidden");
  renderQuizWorkspace();
  document.getElementById("quiz-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderQuizWorkspace() {
  const quiz = state.currentQuiz;
  if (!quiz) return;

  const metaBadges = document.getElementById("quiz-meta-badges");
  metaBadges.innerHTML = `
    <span class="tag tag-primary">${escapeHtml(quiz.subject)}</span>
    <span class="tag">${escapeHtml(TYPE_LABEL[quiz.question_type] || quiz.question_type)}</span>
    <span class="tag">난이도: ${escapeHtml(DIFFICULTY_LABEL[quiz.difficulty] || quiz.difficulty)}</span>
    <span class="tag">${quiz.questions.length}문항</span>
  `;

  document.getElementById("quiz-title-display").textContent = `[${quiz.subject}] ${quiz.unit}`;

  const scoreBanner = document.getElementById("score-banner");
  const submitBtn = document.getElementById("btn-submit-quiz");
  const retryBtn = document.getElementById("btn-retry-quiz");

  if (state.isSubmitted) {
    const total = quiz.questions.length;
    const correctCount = quiz.questions.filter(
      (q) => normalizeAnswerText(state.userAnswers[q.id]) === normalizeAnswerText(q.answer)
    ).length;
    const pct = total ? Math.round((correctCount / total) * 100) : 0;
    scoreBanner.innerHTML = `
      <span>채점 결과: ${total}문항 중 ${correctCount}문항 정답 (${pct}점)</span>
      <span class="muted">각 문항 아래에서 상세 해설을 확인하세요.</span>
    `;
    scoreBanner.classList.remove("hidden");
    submitBtn.classList.add("hidden");
    retryBtn.classList.remove("hidden");
  } else {
    scoreBanner.classList.add("hidden");
    submitBtn.classList.remove("hidden");
    retryBtn.classList.add("hidden");
  }

  const container = document.getElementById("questions-container");
  container.innerHTML = "";

  quiz.questions.forEach((q, idx) => {
    const userAns = state.userAnswers[q.id] ?? "";
    const isCorrect =
      state.isSubmitted && normalizeAnswerText(userAns) === normalizeAnswerText(q.answer);
    const showExplanation = state.isSubmitted || state.previewAnswers;

    const card = document.createElement("article");
    card.className = "card question-card";
    if (state.isSubmitted) {
      card.classList.add(isCorrect ? "correct" : "wrong");
    }

    let resultBadgeHtml = "";
    if (state.isSubmitted) {
      resultBadgeHtml = isCorrect
        ? `<span class="q-result-badge correct">정답</span>`
        : `<span class="q-result-badge wrong">오답</span>`;
    }

    let answerInputHtml = "";
    if (q.type === "multiple_choice" && Array.isArray(q.options)) {
      answerInputHtml = `<div class="options-list">
        ${q.options
          .map((opt, optIdx) => {
            const checked = userAns === opt ? "checked" : "";
            const disabled = state.isSubmitted ? "disabled" : "";
            let optClass = "option-item";
            if (showExplanation && normalizeAnswerText(opt) === normalizeAnswerText(q.answer)) {
              optClass += " is-correct-answer";
            } else if (state.isSubmitted && userAns === opt && !isCorrect) {
              optClass += " is-wrong-choice";
            }
            return `
              <label class="${optClass}">
                <input type="radio" name="q_${q.id}" value="${escapeHtml(opt)}" ${checked} ${disabled} data-qid="${q.id}" />
                <span><strong>${optIdx + 1}.</strong> ${escapeHtml(opt)}</span>
              </label>
            `;
          })
          .join("")}
      </div>`;
    } else {
      const disabled = state.isSubmitted ? "disabled" : "";
      answerInputHtml = `
        <input
          type="text"
          class="short-answer-input"
          data-qid="${q.id}"
          value="${escapeHtml(userAns)}"
          placeholder="정답을 입력하세요..."
          ${disabled}
        />
      `;
    }

    let explanationHtml = "";
    if (showExplanation) {
      explanationHtml = `
        <div class="explanation-box">
          <div class="explanation-answer">정답: ${escapeHtml(q.answer)}</div>
          <p class="explanation-text"><strong>해설:</strong> ${escapeHtml(q.explanation)}</p>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="q-header">
        <span class="q-num">문제 ${idx + 1}</span>
        ${resultBadgeHtml}
      </div>
      <p class="q-text">${escapeHtml(q.question)}</p>
      ${answerInputHtml}
      ${explanationHtml}
    `;

    container.appendChild(card);
  });

  // Bind answer input events
  container.querySelectorAll('input[type="radio"]').forEach((radio) => {
    radio.addEventListener("change", (e) => {
      const qid = Number(e.target.dataset.qid);
      state.userAnswers[qid] = e.target.value;
    });
  });

  container.querySelectorAll(".short-answer-input").forEach((input) => {
    input.addEventListener("input", (e) => {
      const qid = Number(e.target.dataset.qid);
      state.userAnswers[qid] = e.target.value;
    });
  });
}

// ---------- Gallery ----------
function saveCurrentQuizToGallery() {
  if (!state.currentQuiz) return;
  const q = state.currentQuiz;
  const item = {
    id: `quiz_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    title: `[${q.subject}] ${q.unit}`,
    createdAt: new Date().toISOString(),
    quiz: q,
  };
  state.gallery.unshift(item);
  persistGallery();
  showToast("갤러리에 저장되었습니다!");
}

function renderGallery() {
  const grid = document.getElementById("gallery-grid");
  const emptyBox = document.getElementById("gallery-empty");
  const keyword = document.getElementById("gallery-search").value.trim().toLowerCase();
  const typeFilter = document.getElementById("gallery-type-filter").value;

  const filtered = state.gallery.filter((item) => {
    const q = item.quiz;
    const matchesType = typeFilter === "all" || q.question_type === typeFilter;
    const matchesKeyword =
      !keyword ||
      item.title.toLowerCase().includes(keyword) ||
      q.subject.toLowerCase().includes(keyword) ||
      q.unit.toLowerCase().includes(keyword);
    return matchesType && matchesKeyword;
  });

  grid.innerHTML = "";
  if (filtered.length === 0) {
    emptyBox.classList.remove("hidden");
    return;
  }
  emptyBox.classList.add("hidden");

  filtered.forEach((item) => {
    const q = item.quiz;
    const dateStr = new Date(item.createdAt).toLocaleString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });

    const card = document.createElement("article");
    card.className = "card gallery-card";
    card.innerHTML = `
      <div>
        <div class="meta-badges">
          <span class="tag tag-primary">${escapeHtml(q.subject)}</span>
          <span class="tag">${escapeHtml(TYPE_LABEL[q.question_type] || q.question_type)}</span>
          <span class="tag">${q.questions.length}문항</span>
        </div>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="gallery-date">저장일: ${escapeHtml(dateStr)}</p>
      </div>
      <div class="gallery-card-actions">
        <button type="button" class="btn btn-primary btn-sm" data-action="solve" data-id="${item.id}">다시 풀기</button>
        <button type="button" class="btn btn-secondary btn-sm" data-action="view" data-id="${item.id}">해설 보기</button>
        <button type="button" class="btn btn-danger btn-sm" data-action="delete" data-id="${item.id}">삭제</button>
      </div>
    `;

    card.querySelectorAll("button[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => handleGalleryAction(btn.dataset.action, btn.dataset.id));
    });

    grid.appendChild(card);
  });
}

function handleGalleryAction(action, id) {
  const target = state.gallery.find((item) => item.id === id);
  if (!target) return;

  if (action === "solve") {
    switchTab("generator");
    loadQuizIntoWorkspace(target.quiz, { previewAnswers: false });
  } else if (action === "view") {
    switchTab("generator");
    loadQuizIntoWorkspace(target.quiz, { previewAnswers: true });
  } else if (action === "delete") {
    if (!confirm(`"${target.title}" 퀴즈를 갤러리에서 삭제할까요?`)) return;
    state.gallery = state.gallery.filter((item) => item.id !== id);
    persistGallery();
    renderGallery();
    showToast("퀴즈가 삭제되었습니다.");
  }
}

function exportGalleryJson() {
  if (state.gallery.length === 0) {
    showToast("내보낼 퀴즈가 없습니다.");
    return;
  }
  const blob = new Blob([JSON.stringify(state.gallery, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `quiz-gallery-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function importGalleryJson(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const imported = JSON.parse(String(reader.result));
      if (!Array.isArray(imported)) throw new Error("Invalid format");
      const valid = imported.filter((x) => x && x.quiz && Array.isArray(x.quiz.questions));
      if (valid.length === 0) throw new Error("No valid quizzes");
      const existingIds = new Set(state.gallery.map((x) => x.id));
      const newItems = valid.filter((x) => !existingIds.has(x.id));
      state.gallery = [...newItems, ...state.gallery];
      persistGallery();
      renderGallery();
      showToast(`${newItems.length}개의 퀴즈를 가져왔습니다.`);
    } catch {
      showToast("올바른 갤러리 JSON 파일이 아닙니다.");
    } finally {
      event.target.value = "";
    }
  };
  reader.readAsText(file);
}

// ---------- Init ----------
document.addEventListener("DOMContentLoaded", () => {
  loadGallery();
  checkServerHealth();

  document.getElementById("tab-generator").addEventListener("click", () => switchTab("generator"));
  document.getElementById("tab-gallery").addEventListener("click", () => switchTab("gallery"));
  document.getElementById("brand-home").addEventListener("click", () => switchTab("generator"));
  document.getElementById("btn-go-generator").addEventListener("click", () => switchTab("generator"));

  document.querySelectorAll(".preset-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.getElementById("input-subject").value = chip.dataset.subject;
      document.getElementById("input-unit").value = chip.dataset.unit;
    });
  });

  document.getElementById("quiz-form").addEventListener("submit", handleGenerateSubmit);

  document.getElementById("toggle-preview-answers").addEventListener("change", (e) => {
    state.previewAnswers = e.target.checked;
    renderQuizWorkspace();
  });

  document.getElementById("btn-save-gallery").addEventListener("click", saveCurrentQuizToGallery);

  document.getElementById("btn-submit-quiz").addEventListener("click", () => {
    state.isSubmitted = true;
    renderQuizWorkspace();
    document.getElementById("score-banner").scrollIntoView({ behavior: "smooth", block: "center" });
  });

  document.getElementById("btn-retry-quiz").addEventListener("click", () => {
    state.userAnswers = {};
    state.isSubmitted = false;
    renderQuizWorkspace();
  });

  document.getElementById("gallery-search").addEventListener("input", renderGallery);
  document.getElementById("gallery-type-filter").addEventListener("change", renderGallery);
  document.getElementById("btn-export-gallery").addEventListener("click", exportGalleryJson);
  document.getElementById("input-import-gallery").addEventListener("change", importGalleryJson);
});
