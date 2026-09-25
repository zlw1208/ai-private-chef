const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const elements = {
  dropzone: document.querySelector("#dropzone"),
  input: document.querySelector("#image-input"),
  emptyPreview: document.querySelector("#empty-preview"),
  selectedPreview: document.querySelector("#selected-preview"),
  previewImage: document.querySelector("#preview-image"),
  fileName: document.querySelector("#file-name"),
  fileDetails: document.querySelector("#file-details"),
  removeFile: document.querySelector("#remove-file"),
  uploadButton: document.querySelector("#upload-button"),
  errorAlert: document.querySelector("#error-alert"),
  errorMessage: document.querySelector("#error-message"),
  progressPanel: document.querySelector("#progress-panel"),
  progressSummary: document.querySelector("#progress-summary"),
  successPanel: document.querySelector("#success-panel"),
  resultType: document.querySelector("#result-type"),
  resultSize: document.querySelector("#result-size"),
  resultKey: document.querySelector("#result-key"),
  recognitionSummary: document.querySelector("#recognition-summary"),
  recognitionNote: document.querySelector("#recognition-note"),
  ingredientList: document.querySelector("#ingredient-list"),
  uploadAnother: document.querySelector("#upload-another"),
  recipeMessage: document.querySelector("#recipe-message"),
  recipeButton: document.querySelector("#recipe-button"),
  ingredientContext: document.querySelector("#ingredient-context"),
  recipeStatus: document.querySelector("#recipe-status"),
  recipeResult: document.querySelector("#recipe-result"),
  recipeSummary: document.querySelector("#recipe-summary"),
  toolBadge: document.querySelector("#tool-badge"),
  toolReason: document.querySelector("#tool-reason"),
  recipeList: document.querySelector("#recipe-list"),
  safetyNote: document.querySelector("#safety-note"),
};

let selectedFile = null;
let previewUrl = null;
let currentIngredients = [];
let currentImageContext = null;
const threadId = sessionStorage.getItem("ai-chef-thread-id") || crypto.randomUUID();
sessionStorage.setItem("ai-chef-thread-id", threadId);

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function showError(message) {
  elements.errorMessage.textContent = message;
  elements.errorAlert.hidden = false;
}

function clearError() {
  elements.errorAlert.hidden = true;
  elements.errorMessage.textContent = "";
}

function validateFile(file) {
  if (!ALLOWED_TYPES.has(file.type)) {
    throw new Error("暂不支持这种图片格式，请选择 JPEG、PNG 或 WEBP。");
  }
  if (file.size <= 0) {
    throw new Error("图片内容为空，请重新选择。");
  }
  if (file.size > MAX_FILE_SIZE) {
    throw new Error("图片超过 10 MB，请压缩后再上传。");
  }
}

function selectFile(file) {
  clearError();
  try {
    validateFile(file);
  } catch (error) {
    resetSelection();
    showError(error.message);
    return;
  }

  selectedFile = file;
  currentIngredients = [];
  currentImageContext = null;
  elements.ingredientContext.textContent = "新图片尚未识别，识别完成后将更新食材。";
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  elements.previewImage.src = previewUrl;
  elements.fileName.textContent = file.name;
  elements.fileDetails.textContent = `${file.type} · ${formatBytes(file.size)}`;
  elements.emptyPreview.hidden = true;
  elements.selectedPreview.hidden = false;
  elements.uploadButton.disabled = false;
  elements.successPanel.hidden = true;
}

function resetSelection() {
  selectedFile = null;
  elements.input.value = "";
  elements.uploadButton.disabled = true;
  elements.uploadButton.classList.remove("is-loading");
  elements.emptyPreview.hidden = false;
  elements.selectedPreview.hidden = true;
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }
  elements.previewImage.removeAttribute("src");
}

function setProgress(stepName) {
  const steps = [...document.querySelectorAll("[data-progress]")];
  const activeIndex = steps.findIndex((step) => step.dataset.progress === stepName);
  steps.forEach((step, index) => {
    step.classList.toggle("is-complete", index < activeIndex);
    step.classList.toggle("is-active", index === activeIndex);
  });
  const summaries = {
    validate: "正在检查",
    presign: "正在申请上传授权",
    upload: "正在上传",
    verify: "正在校验",
    recognize: "正在识别食材",
  };
  elements.progressSummary.textContent = summaries[stepName];
}

function finishProgress() {
  document.querySelectorAll("[data-progress]").forEach((step) => {
    step.classList.remove("is-active");
    step.classList.add("is-complete");
  });
  elements.progressSummary.textContent = "全部完成";
}

async function parseError(response, fallback) {
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch {
    return fallback;
  }
}

async function requestUploadTicket(file) {
  const response = await fetch("/api/uploads/presign", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      size_bytes: file.size,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "无法获取上传授权，请稍后重试。"));
  }
  return response.json();
}

async function uploadToOss(ticket, file) {
  const response = await fetch(ticket.upload_url, {
    method: ticket.method,
    headers: ticket.headers,
    body: file,
  });
  if (!response.ok) {
    throw new Error(`OSS 上传失败（${response.status}），请检查 Bucket CORS 配置。`);
  }
}

async function completeUpload(objectKey) {
  const response = await fetch("/api/uploads/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ object_key: objectKey }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "图片校验失败，请重新上传。"));
  }
  return response.json();
}

async function recognizeIngredients(objectKey) {
  const response = await fetch("/api/recognitions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      object_key: objectKey,
      user_text: "",
      thread_id: threadId,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "食材识别失败，请稍后重试。"));
  }
  return response.json();
}

function renderRecognition(payload) {
  const recognition = payload.recognition;
  currentImageContext = {
    is_food_image: recognition.is_food_image,
    summary: recognition.summary,
  };
  currentIngredients = recognition.ingredients.map((ingredient) => ({
    name: ingredient.name_zh,
    quantity: ingredient.quantity_estimate,
    state: ingredient.visible_state,
  }));
  elements.recognitionSummary.textContent = recognition.summary;
  elements.recognitionNote.textContent = recognition.uncertainty_note ||
    (recognition.is_food_image ? "你可以在下一步确认或修改这些食材。" : "");
  elements.ingredientList.replaceChildren();
  elements.ingredientContext.textContent = currentIngredients.length > 0
    ? `已加入 ${currentIngredients.length} 种图片食材：${currentIngredients.map((item) => item.name).join("、")}`
    : "图片中未识别到可用食材，可直接在下方描述。";

  if (!recognition.is_food_image || recognition.ingredients.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-recognition";
    empty.textContent = "没有识别到明确食材，请换一张光线更好、主体更清晰的照片。";
    elements.ingredientList.append(empty);
    return;
  }

  recognition.ingredients.forEach((ingredient) => {
    const confidence = Math.round(ingredient.confidence * 100);
    const card = document.createElement("article");
    card.className = "ingredient-card";

    const header = document.createElement("div");
    header.className = "ingredient-card-header";
    const name = document.createElement("h3");
    name.textContent = ingredient.name_zh;
    const score = document.createElement("span");
    score.textContent = `${confidence}%`;
    header.append(name, score);

    const description = document.createElement("p");
    description.textContent = `${ingredient.quantity_estimate} · ${ingredient.visible_state}`;

    const track = document.createElement("div");
    track.className = "confidence-track";
    const fill = document.createElement("span");
    fill.style.width = `${confidence}%`;
    track.append(fill);

    card.append(header, description, track);
    elements.ingredientList.append(card);
  });
}

async function requestRecipe(message) {
  const response = await fetch("/api/recipes/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      ingredients: currentIngredients,
      image_context: currentImageContext,
      thread_id: threadId,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "菜谱生成失败，请稍后重试。"));
  }
  return response.json();
}

function appendTextList(container, title, items, ordered = false) {
  if (!items.length) return;
  const heading = document.createElement("h4");
  heading.textContent = title;
  const list = document.createElement(ordered ? "ol" : "ul");
  items.forEach((item) => {
    const row = document.createElement("li");
    row.textContent = item;
    list.append(row);
  });
  container.append(heading, list);
}

function renderRecipe(payload) {
  const recommendation = payload.recommendation;
  elements.recipeSummary.textContent = recommendation.summary;
  elements.toolBadge.textContent = payload.tool_used === "tavily"
    ? "Tavily 已调用"
    : "本地模型知识";
  elements.toolBadge.classList.toggle("used-tavily", payload.tool_used === "tavily");
  elements.toolReason.textContent = payload.tool_reason;
  elements.safetyNote.textContent = recommendation.safety_note;
  elements.recipeList.replaceChildren();

  recommendation.recipes.forEach((recipe) => {
    const card = document.createElement("article");
    card.className = "recipe-card";

    const heading = document.createElement("div");
    heading.className = "recipe-card-heading";
    const title = document.createElement("h3");
    title.textContent = recipe.title;
    const meta = document.createElement("span");
    meta.textContent = `${recipe.total_time_minutes} 分钟 · ${recipe.difficulty} · ${recipe.servings}`;
    heading.append(title, meta);

    const rationale = document.createElement("p");
    rationale.textContent = recipe.rationale;
    card.append(heading, rationale);
    appendTextList(
      card,
      "食材用量",
      recipe.ingredients.map((item) => `${item.name}：${item.amount}`),
    );
    appendTextList(card, "做法", recipe.steps, true);
    appendTextList(card, "替代方案", recipe.substitutions);
    appendTextList(card, "私厨提示", recipe.tips);

    const validSources = recipe.source_urls.filter((url) => {
      try {
        return ["http:", "https:"].includes(new URL(url).protocol);
      } catch {
        return false;
      }
    });
    if (validSources.length > 0) {
      const sourceHeading = document.createElement("h4");
      sourceHeading.textContent = "参考来源";
      const sources = document.createElement("div");
      sources.className = "recipe-sources";
      validSources.forEach((url, index) => {
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = `来源 ${index + 1} ↗`;
        sources.append(link);
      });
      card.append(sourceHeading, sources);
    }
    elements.recipeList.append(card);
  });
  elements.recipeResult.hidden = false;
  elements.recipeResult.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function handleRecipeRequest() {
  const message = elements.recipeMessage.value.trim();
  if (!message) {
    showError("请先描述食材、口味或想吃的菜。");
    elements.recipeMessage.focus();
    return;
  }

  clearError();
  elements.recipeButton.disabled = true;
  elements.recipeButton.classList.add("is-loading");
  elements.recipeStatus.textContent = "Agent 正在判断是否需要调用 Tavily……";
  elements.recipeStatus.hidden = false;
  elements.recipeResult.hidden = true;
  try {
    const payload = await requestRecipe(message);
    elements.recipeStatus.hidden = true;
    renderRecipe(payload);
  } catch (error) {
    elements.recipeStatus.textContent = "生成失败";
    showError(error instanceof Error ? error.message : "菜谱生成失败。");
  } finally {
    elements.recipeButton.classList.remove("is-loading");
    elements.recipeButton.disabled = false;
  }
}

async function handleUpload() {
  if (!selectedFile) return;

  clearError();
  elements.successPanel.hidden = true;
  elements.progressPanel.hidden = false;
  elements.uploadButton.disabled = true;
  elements.uploadButton.classList.add("is-loading");

  try {
    setProgress("validate");
    validateFile(selectedFile);

    setProgress("presign");
    const ticket = await requestUploadTicket(selectedFile);

    setProgress("upload");
    await uploadToOss(ticket, selectedFile);

    setProgress("verify");
    const uploadResult = await completeUpload(ticket.object_key);

    setProgress("recognize");
    const recognitionResult = await recognizeIngredients(ticket.object_key);

    finishProgress();
    renderRecognition(recognitionResult);
    elements.resultType.textContent = uploadResult.content_type;
    elements.resultSize.textContent = formatBytes(uploadResult.size_bytes);
    elements.resultKey.textContent = uploadResult.object_key;
    elements.successPanel.hidden = false;
    elements.successPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    showError(error instanceof Error ? error.message : "上传失败，请稍后重试。");
    elements.progressSummary.textContent = "处理失败";
  } finally {
    elements.uploadButton.classList.remove("is-loading");
    elements.uploadButton.disabled = !selectedFile;
  }
}

elements.input.addEventListener("change", (event) => {
  const [file] = event.target.files;
  if (file) selectFile(file);
});

elements.removeFile.addEventListener("click", (event) => {
  event.preventDefault();
  resetSelection();
  clearError();
});

elements.uploadButton.addEventListener("click", handleUpload);

elements.uploadAnother.addEventListener("click", () => {
  resetSelection();
  clearError();
  elements.progressPanel.hidden = true;
  elements.successPanel.hidden = true;
  elements.dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
});

elements.recipeButton.addEventListener("click", handleRecipeRequest);

["dragenter", "dragover"].forEach((eventName) => {
  elements.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropzone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  elements.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropzone.classList.remove("is-dragging");
  });
});

elements.dropzone.addEventListener("drop", (event) => {
  const [file] = event.dataTransfer.files;
  if (file) selectFile(file);
});
