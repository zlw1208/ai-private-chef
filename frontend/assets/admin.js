const elements = {
  environment: document.querySelector("#environment"),
  backend: document.querySelector("#backend"),
  threadCount: document.querySelector("#thread-count"),
  checkpointCount: document.querySelector("#checkpoint-count"),
  table: document.querySelector("#thread-table"),
  empty: document.querySelector("#empty-state"),
  error: document.querySelector("#admin-error"),
  search: document.querySelector("#thread-search"),
  refresh: document.querySelector("#refresh-button"),
  detail: document.querySelector("#detail-panel"),
  detailMeta: document.querySelector("#detail-meta"),
  detailJson: document.querySelector("#detail-json"),
  closeDetail: document.querySelector("#close-detail"),
};

let threads = [];

function formatDate(value) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "medium",
    hour12: false,
  }).format(new Date(value));
}

function kindLabel(kind) {
  return { recognition: "图片识别", recipes: "菜谱对话", other: "其他" }[kind] || kind;
}

function renderThreads(items) {
  elements.table.replaceChildren();
  elements.empty.hidden = items.length > 0;
  items.forEach((thread) => {
    const row = document.createElement("tr");
    const kindCell = document.createElement("td");
    const kind = document.createElement("span");
    kind.className = `kind ${thread.kind}`;
    kind.textContent = kindLabel(thread.kind);
    kindCell.append(kind);

    const idCell = document.createElement("td");
    idCell.className = "thread-id";
    idCell.title = thread.thread_id;
    idCell.textContent = thread.thread_id;

    const countCell = document.createElement("td");
    countCell.textContent = String(thread.checkpoint_count);
    const dateCell = document.createElement("td");
    dateCell.textContent = formatDate(thread.last_updated_at);

    const actionCell = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "view-button";
    button.textContent = "查看状态";
    button.addEventListener("click", () => loadDetail(thread.thread_id));
    actionCell.append(button);
    row.append(kindCell, idCell, countCell, dateCell, actionCell);
    elements.table.append(row);
  });
}

function renderMeta(detail) {
  elements.detailMeta.replaceChildren();
  const entries = [
    ["Thread ID", detail.thread_id],
    ["会话类型", kindLabel(detail.kind)],
    ["Checkpoint 数", String(detail.checkpoint_count)],
    ["最后更新", formatDate(detail.last_updated_at)],
    ["最新 Checkpoint ID", detail.latest_checkpoint_id],
  ];
  entries.forEach(([label, value]) => {
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    wrapper.append(term, description);
    elements.detailMeta.append(wrapper);
  });
}

async function loadDetail(threadId) {
  elements.error.hidden = true;
  try {
    const response = await fetch(`/api/admin/threads/${encodeURIComponent(threadId)}`);
    if (!response.ok) throw new Error(`读取失败（${response.status}）`);
    const detail = await response.json();
    renderMeta(detail);
    elements.detailJson.textContent = JSON.stringify(detail.latest_state, null, 2);
    elements.detail.hidden = false;
    elements.detail.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    elements.error.textContent = error.message;
    elements.error.hidden = false;
  }
}

async function loadOverview() {
  elements.refresh.disabled = true;
  elements.error.hidden = true;
  try {
    const response = await fetch("/api/admin/overview");
    if (!response.ok) throw new Error(`后台数据读取失败（${response.status}）`);
    const overview = await response.json();
    elements.environment.textContent = overview.environment.toUpperCase();
    elements.backend.textContent = overview.checkpointer_backend.toUpperCase();
    elements.threadCount.textContent = String(overview.thread_count);
    elements.checkpointCount.textContent = overview.truncated
      ? `${overview.checkpoint_count}+`
      : String(overview.checkpoint_count);
    threads = overview.threads;
    renderThreads(threads);
  } catch (error) {
    elements.error.textContent = error.message;
    elements.error.hidden = false;
  } finally {
    elements.refresh.disabled = false;
  }
}

elements.search.addEventListener("input", () => {
  const query = elements.search.value.trim().toLowerCase();
  renderThreads(threads.filter((item) => item.thread_id.toLowerCase().includes(query)));
});
elements.refresh.addEventListener("click", loadOverview);
elements.closeDetail.addEventListener("click", () => { elements.detail.hidden = true; });

loadOverview();
