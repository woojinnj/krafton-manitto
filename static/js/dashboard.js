"use strict";

const state = { afterModal: null, cardRequest: 0, profileSaving: false };

function getCookie(name) {
  const prefix = `${name}=`;
  const cookie = document.cookie.split(";").map((item) => item.trim())
    .find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : "";
}

async function apiRequest(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = getCookie("csrf_access_token");
    if (csrfToken) headers.set("X-CSRF-TOKEN", csrfToken);
  }
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, { ...options, headers, signal: controller.signal });
    if (response.status === 401 || response.status === 422) {
      window.location.assign("/login");
      throw new Error("Authentication required");
    }
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("서버 응답을 확인할 수 없습니다. 잠시 후 다시 시도해주세요.");
    }
    if (!response.ok || data.result !== "success") {
      throw new Error(data.message || "요청을 처리하지 못했습니다.");
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("응답이 지연되고 있습니다. 진행 상태를 새로고침해 결과를 확인해주세요.");
    }
    if (error instanceof TypeError) {
      throw new Error("연결을 확인한 뒤 다시 시도해주세요.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function showAlert(message, afterClose = null, confirm = false) {
  const modal = document.getElementById("custom-modal");
  state.afterModal = afterClose;
  document.getElementById("modal-title").textContent = confirm ? "새로 배정할까요?" : "알림";
  document.getElementById("modal-message").textContent = message;
  document.getElementById("modal-cancel").hidden = !confirm;
  document.getElementById("modal-close").textContent = confirm ? "새로 배정" : "확인";
  modal.showModal();
  document.getElementById(confirm ? "modal-cancel" : "modal-close").focus();
}

function closeModal(confirmed = false) {
  const callback = confirmed ? state.afterModal : null;
  state.afterModal = null;
  document.getElementById("custom-modal").close();
  if (callback) callback();
}

function reportError(error) {
  if (error.message !== "Authentication required") showAlert(error.message);
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
}

function hideCard() {
  state.cardRequest += 1;
  const card = document.getElementById("manitto-card");
  card.classList.remove("flipped");
  card.querySelector(".card-front").removeAttribute("aria-hidden");
  card.querySelector(".card-back").setAttribute("aria-hidden", "true");
  card.querySelector(".card-back").inert = true;
  document.getElementById("hide-card").hidden = true;
  document.querySelectorAll("[data-card]").forEach((button) => {
    button.setAttribute("aria-pressed", "false");
  });
}

async function loadCard(kind) {
  const requestId = ++state.cardRequest;
  const isManitti = kind === "manitti";
  const buttons = document.querySelectorAll("[data-card]");
  buttons.forEach((button) => setBusy(button, true));
  try {
    const data = await apiRequest(isManitti ? "/dashboard/showManitti" : "/dashboard/showManitto");
    if (requestId !== state.cardRequest) return;
    document.getElementById("card-label").textContent = isManitti ? "나를 응원한 친구" : "내가 응원할 친구";
    document.getElementById("card-title").textContent = isManitti ? "내 마니띠" : "내 마니또";
    document.getElementById("card-name").textContent = data.user.name;
    document.getElementById("card-mbti").textContent = data.user.mbti;
    document.getElementById("card-want").textContent = data.user.want;
    document.getElementById("manitti-extra").hidden = !isManitti || data.rated;
    document.getElementById("rating-complete").hidden = !isManitti || !data.rated;
    document.querySelectorAll('input[name="rating"]').forEach((input) => { input.checked = false; });
    document.getElementById("rating-emoji").textContent = "🙂";
    const card = document.getElementById("manitto-card");
    card.querySelector(".card-front").setAttribute("aria-hidden", "true");
    card.querySelector(".card-back").removeAttribute("aria-hidden");
    card.querySelector(".card-back").inert = false;
    card.classList.add("flipped");
    document.getElementById("hide-card").hidden = false;
    buttons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.card === kind)));
  } catch (error) {
    if (requestId === state.cardRequest) reportError(error);
  } finally {
    buttons.forEach((button) => setBusy(button, false));
  }
}

async function submitRating(button) {
  const selected = document.querySelector('input[name="rating"]:checked');
  if (!selected) return showAlert("별점을 선택해주세요.");
  setBusy(button, true);
  try {
    await apiRequest("/api/likes", { method: "POST", body: new URLSearchParams({ like: selected.value }) });
    document.getElementById("manitti-extra").hidden = true;
    document.getElementById("rating-complete").hidden = false;
    showAlert("별점이 등록되었습니다. 고마운 마음이 랭킹에 반영됐어요.", () => window.location.reload());
  } catch (error) {
    reportError(error);
  } finally {
    setBusy(button, false);
  }
}

async function runAdminAction(url, successMessage) {
  const buttons = document.querySelectorAll(".admin-actions button");
  buttons.forEach((button) => setBusy(button, true));
  try {
    const data = await apiRequest(url, { method: "POST" });
    hideCard();
    showAlert(typeof successMessage === "function" ? successMessage(data) : successMessage,
      () => window.location.reload());
  } catch (error) {
    reportError(error);
  } finally {
    buttons.forEach((button) => setBusy(button, false));
  }
}

function updateWantCount() {
  document.getElementById("want-count").textContent = `${document.getElementById("edit-want").value.length} / 100자`;
}

async function saveProfile(event) {
  event.preventDefault();
  if (state.profileSaving) return;
  const form = event.currentTarget;
  const body = new URLSearchParams(new FormData(form));
  const errorMessage = document.getElementById("profile-error");
  errorMessage.hidden = true;
  state.profileSaving = true;
  const controls = form.querySelectorAll("input, select, textarea, button");
  controls.forEach((control) => { control.disabled = true; });
  setBusy(document.getElementById("profile-save"), true);
  try {
    await apiRequest("/dashboard/side/update", { method: "PUT", body });
    const name = body.get("name").trim();
    const want = body.get("want").trim();
    document.querySelectorAll("[data-profile-name]").forEach((element) => { element.textContent = name; });
    document.getElementById("profile-avatar").textContent = Array.from(name)[0];
    document.getElementById("profile-mbti").textContent = body.get("mbti");
    document.getElementById("profile-want").textContent = `“${want}”`;
    form.elements.name.value = name;
    form.elements.want.value = want;
    // Reset should restore the most recently saved profile when reopening the editor.
    form.querySelectorAll("input, textarea").forEach((input) => { input.defaultValue = input.value; });
    form.querySelectorAll("option").forEach((option) => { option.defaultSelected = option.value === body.get("mbti"); });
    document.getElementById("profile-dialog").close();
    document.getElementById("profile-status").textContent = "✓ 프로필을 저장했습니다.";
  } catch (error) {
    if (error.message !== "Authentication required") {
      errorMessage.textContent = error.message;
      errorMessage.hidden = false;
    }
  } finally {
    state.profileSaving = false;
    controls.forEach((control) => { control.disabled = false; });
    setBusy(document.getElementById("profile-save"), false);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-card]").forEach((button) => {
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => loadCard(button.dataset.card));
  });
  document.getElementById("hide-card").addEventListener("click", () => {
    hideCard();
    document.querySelector("[data-card]").focus();
  });
  document.getElementById("rating-submit").addEventListener("click", (event) => submitRating(event.currentTarget));
  document.getElementById("shuffle-button")?.addEventListener("click", () => {
    showAlert("현재 배정이 새 배정으로 바뀌고 마니띠는 비공개로 전환됩니다. 이번 배정의 별점 등록 기회가 초기화되며, 누적 랭킹은 유지됩니다.",
      () => runAdminAction("/api/shuffle", "새로운 마니또 배정이 완료되었습니다."), true);
  });
  document.getElementById("toggle-button")?.addEventListener("click", () => {
    runAdminAction("/api/toggle-open", (data) => `마니띠를 ${data.is_open ? "공개" : "비공개"} 상태로 전환했습니다.`);
  });
  document.getElementById("modal-close").addEventListener("click", () => closeModal(true));
  document.getElementById("modal-cancel").addEventListener("click", () => closeModal());
  document.getElementById("custom-modal").addEventListener("cancel", (event) => {
    event.preventDefault();
    // Escape acknowledges informational messages, but cancels confirmations.
    closeModal(document.getElementById("modal-cancel").hidden);
  });
  document.getElementById("profile-edit").addEventListener("click", () => {
    document.getElementById("profile-form").reset();
    document.getElementById("profile-error").hidden = true;
    document.getElementById("profile-status").textContent = "";
    updateWantCount();
    document.getElementById("profile-dialog").showModal();
  });
  document.getElementById("profile-cancel").addEventListener("click", () => document.getElementById("profile-dialog").close());
  document.getElementById("profile-dialog").addEventListener("cancel", (event) => {
    if (state.profileSaving) event.preventDefault();
  });
  document.getElementById("profile-form").addEventListener("submit", saveProfile);
  document.getElementById("edit-want").addEventListener("input", updateWantCount);
  document.querySelector(".star-rating").addEventListener("change", (event) => {
    const emojis = ["🙂", "😭", "😢", "🙂", "😄", "😍"];
    document.getElementById("rating-emoji").textContent = emojis[Number(event.target.value)] || emojis[0];
  });
});
