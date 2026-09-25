const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const THREAD_KEY = "ai-chef-chat-thread-id";

const elements = {
  composer: document.querySelector("#composer"),
  input: document.querySelector("#message-input"),
  imageInput: document.querySelector("#image-input"),
  sendButton: document.querySelector("#send-button"),
  removeAttachment: document.querySelector("#remove-attachment"),
  attachmentPreview: document.querySelector("#attachment-preview"),
  attachmentImage: document.querySelector("#attachment-image"),
  attachmentName: document.querySelector("#attachment-name"),
  composerHint: document.querySelector("#composer-hint"),
  emptyState: document.querySelector("#empty-state"),
  conversation: document.querySelector("#conversation"),
};

let selectedFile = null;
let previewUrl = null;
let busy = false;

function getThreadId() {
  let threadId = sessionStorage.getItem(THREAD_KEY);
  if (!threadId) {
    threadId = crypto.randomUUID();
    sessionStorage.setItem(THREAD_KEY, threadId);
  }
  return threadId;
}

function setHint(message, isError = false) {
  elements.composerHint.textContent = message;
  elements.composerHint.classList.toggle("error", isError);
}

function validateImage(file) {
  if (!ALLOWED_TYPES.has(file.type)) {
    throw new Error("请选择 JPG、PNG 或 WEBP 图片。");
  }
  if (file.size > MAX_FILE_SIZE) {
    throw new Error("图片不能超过 10 MB。");
  }
}

function clearAttachment() {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  selectedFile = null;
  elements.imageInput.value = "";
  elements.attachmentPreview.hidden = true;
  elements.attachmentImage.removeAttribute("src");
  setHint("支持 JPG、PNG、WEBP，最大 10 MB");
}

function selectImage(file) {
  try {
    validateImage(file);
    clearAttachment();
    selectedFile = file;
    previewUrl = URL.createObjectURL(file);
    elements.attachmentImage.src = previewUrl;
    elements.attachmentName.textContent = file.name;
    elements.attachmentPreview.hidden = false;
    setHint("图片已添加，可继续输入要求或直接发送");
    elements.input.focus();
  } catch (error) {
    setHint(error.message, true);
  }
}

function resizeInput() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 160)}px`;
}

function scrollToLatest() {
  requestAnimationFrame(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }));
}

function addUserMessage(message, file) {
  elements.emptyState.hidden = true;
  const article = document.createElement("article");
  article.className = "message user";
  const bubble = document.createElement("div");
  bubble.className = "user-bubble";
  if (file) {
    const image = document.createElement("img");
    const displayUrl = URL.createObjectURL(file);
    image.src = displayUrl;
    image.alt = "用户上传的图片";
    image.addEventListener("load", () => URL.revokeObjectURL(displayUrl), { once: true });
    bubble.append(image);
  }
  if (message) {
    const text = document.createElement("span");
    text.textContent = message;
    bubble.append(text);
  }
  article.append(bubble);
  elements.conversation.append(article);
  scrollToLatest();
}

function addAssistantMessage() {
  const article = document.createElement("article");
  article.className = "message assistant";
  const avatar = document.createElement("div");
  avatar.className = "assistant-avatar";
  avatar.textContent = "厨";
  const body = document.createElement("div");
  body.className = "assistant-body";
  const status = document.createElement("p");
  status.className = "assistant-status working";
  status.textContent = "正在准备";
  const content = document.createElement("pre");
  content.className = "assistant-content";
  const meta = document.createElement("span");
  meta.className = "assistant-meta";
  meta.hidden = true;
  body.append(status, content, meta);
  article.append(avatar, body);
  elements.conversation.append(article);
  scrollToLatest();
  return { article, status, content, meta };
}

async function parseError(response, fallback) {
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch {
    return fallback;
  }
}

async function uploadImage(file, assistant) {
  assistant.status.textContent = "正在申请图片上传授权";
  const presignResponse = await fetch("/api/uploads/presign", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      size_bytes: file.size,
    }),
  });
  if (!presignResponse.ok) {
    throw new Error(await parseError(presignResponse, "无法获取图片上传授权。"));
  }
  const ticket = await presignResponse.json();

  assistant.status.textContent = "正在安全上传图片";
  const uploadResponse = await fetch(ticket.upload_url, {
    method: ticket.method,
    headers: ticket.headers,
    body: file,
  });
  if (!uploadResponse.ok) {
    throw new Error(`图片上传失败（${uploadResponse.status}），请检查 OSS CORS 配置。`);
  }

  assistant.status.textContent = "正在校验图片";
  const completeResponse = await fetch("/api/uploads/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ object_key: ticket.object_key }),
  });
  if (!completeResponse.ok) {
    throw new Error(await parseError(completeResponse, "图片校验失败，请重新上传。"));
  }
  return ticket.object_key;
}

function handleStreamEvent(event, assistant) {
  if (event.type === "status") {
    assistant.status.textContent = event.message;
  } else if (event.type === "recognition") {
    assistant.status.textContent = event.summary;
  } else if (event.type === "meta") {
    assistant.meta.hidden = false;
    assistant.meta.textContent = event.tool_used === "tavily" ? "已调用 Tavily" : "基于模型知识";
  } else if (event.type === "delta") {
    assistant.status.hidden = true;
    assistant.content.textContent += event.content;
    scrollToLatest();
  } else if (event.type === "done") {
    assistant.status.classList.remove("working");
    if (!assistant.content.textContent) assistant.status.textContent = "已完成";
  } else if (event.type === "error") {
    throw new Error(event.message);
  }
}

async function streamChat(message, objectKey, assistant) {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      object_key: objectKey,
      thread_id: getThreadId(),
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "无法连接 AI 私厨。"));
  }
  if (!response.body) throw new Error("当前浏览器不支持流式响应。");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) handleStreamEvent(JSON.parse(line), assistant);
    }
    if (done) break;
  }
  if (buffer.trim()) handleStreamEvent(JSON.parse(buffer), assistant);
}

async function submitMessage(event) {
  event.preventDefault();
  if (busy) return;
  const message = elements.input.value.trim();
  const file = selectedFile;
  if (!message && !file) {
    setHint("请输入文字或添加一张图片。", true);
    elements.input.focus();
    return;
  }

  busy = true;
  elements.sendButton.disabled = true;
  addUserMessage(message, file);
  const assistant = addAssistantMessage();
  elements.input.value = "";
  resizeInput();
  clearAttachment();

  try {
    const objectKey = file ? await uploadImage(file, assistant) : null;
    await streamChat(message, objectKey, assistant);
  } catch (error) {
    assistant.article.classList.add("error");
    assistant.status.hidden = false;
    assistant.status.classList.remove("working");
    assistant.status.textContent = error.message || "处理失败，请稍后重试。";
  } finally {
    busy = false;
    elements.sendButton.disabled = false;
    elements.input.focus();
    scrollToLatest();
  }
}

elements.composer.addEventListener("submit", submitMessage);
elements.input.addEventListener("input", resizeInput);
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    elements.composer.requestSubmit();
  }
});
elements.imageInput.addEventListener("change", () => {
  const [file] = elements.imageInput.files;
  if (file) selectImage(file);
});
elements.removeAttachment.addEventListener("click", clearAttachment);

for (const eventName of ["dragenter", "dragover"]) {
  elements.composer.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.composer.classList.add("is-dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  elements.composer.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.composer.classList.remove("is-dragging");
  });
}
elements.composer.addEventListener("drop", (event) => {
  const [file] = event.dataTransfer.files;
  if (file) selectImage(file);
});

elements.input.focus();
