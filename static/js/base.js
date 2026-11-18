/* 全局基础脚本。
 * 提供跨页面复用的最小工具：CSRF Token 读取、全局命名空间。
 */
(function () {
  "use strict";

  window.App = window.App || {};

  /** 从 Cookie 中读取指定名称的值。 */
  function getCookie(name) {
    if (!document.cookie) return null;
    const prefix = name + "=";
    const parts = document.cookie.split(";");
    for (let i = 0; i < parts.length; i += 1) {
      const part = parts[i].trim();
      if (part.indexOf(prefix) === 0) {
        return part.substring(prefix.length);
      }
    }
    return null;
  }

  // 供 AJAX（fetch）请求携带 CSRF Token 使用
  window.App.getCookie = getCookie;
  window.App.csrfToken = getCookie("csrftoken");
})();
