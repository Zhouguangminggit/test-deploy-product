/* 通用交互逻辑。
 * 1) 确认弹窗：window.confirmDialog(options) 返回 Promise<boolean>
 * 2) 消息提示：自动隐藏与手动关闭（配合 templates/includes/messages.html）
 */
(function () {
  "use strict";

  // ----------------------------- 确认弹窗 -----------------------------
  const modal = document.querySelector("[data-confirm-modal]");

  function confirmDialog(options) {
    options = options || {};
    if (!modal) {
      // 兜底：无自定义弹窗时使用原生 confirm
      return Promise.resolve(window.confirm(options.message || "确定要执行该操作吗？"));
    }

    const titleEl = modal.querySelector("[data-confirm-title]");
    const messageEl = modal.querySelector("[data-confirm-message]");
    const okBtn = modal.querySelector("[data-confirm-ok]");
    const cancelBtn = modal.querySelector("[data-confirm-cancel]");

    if (titleEl) titleEl.textContent = options.title || "确认操作";
    if (messageEl) messageEl.textContent = options.message || "确定要执行该操作吗？";
    if (okBtn) okBtn.textContent = options.okText || "确定";
    if (cancelBtn) cancelBtn.textContent = options.cancelText || "取消";

    return new Promise((resolve) => {
      function open() {
        modal.classList.remove("hidden");
        modal.classList.add("flex");
      }
      function close(result) {
        modal.classList.add("hidden");
        modal.classList.remove("flex");
        okBtn.removeEventListener("click", onOk);
        cancelBtn.removeEventListener("click", onCancel);
        modal.removeEventListener("click", onBackdrop);
        document.removeEventListener("keydown", onKeydown);
        resolve(result);
      }
      function onOk() { close(true); }
      function onCancel() { close(false); }
      function onBackdrop(event) { if (event.target === modal) close(false); }
      function onKeydown(event) { if (event.key === "Escape") close(false); }

      okBtn.addEventListener("click", onOk);
      cancelBtn.addEventListener("click", onCancel);
      modal.addEventListener("click", onBackdrop);
      document.addEventListener("keydown", onKeydown);
      open();
    });
  }

  window.confirmDialog = confirmDialog;

  // 为带有 data-confirm 的元素自动绑定确认行为
  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-confirm]");
    if (!trigger) return;
    event.preventDefault();
    confirmDialog({ message: trigger.getAttribute("data-confirm") }).then(function (ok) {
      if (!ok) return;
      const href = trigger.getAttribute("href");
      if (href) window.location.href = href;
      else if (trigger.form) trigger.form.submit();
    });
  });

  // ----------------------------- 消息提示 -----------------------------
  function dismiss(el) {
    if (!el) return;
    el.style.transition = "opacity 0.3s";
    el.style.opacity = "0";
    window.setTimeout(function () { el.remove(); }, 300);
  }

  document.querySelectorAll("[data-message]").forEach(function (el) {
    const closeBtn = el.querySelector("[data-dismiss]");
    if (closeBtn) closeBtn.addEventListener("click", function () { dismiss(el); });

    const autohide = parseInt(el.getAttribute("data-autohide") || "0", 10);
    if (autohide > 0) window.setTimeout(function () { dismiss(el); }, autohide);
  });
})();
