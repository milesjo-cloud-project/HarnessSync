/* Static local translations. Climb values and user text are never translated. */
"use strict";
const hsLanguages = {en: "English", es: "Español", fr: "Français", ja: "日本語", ko: "한국어", zh: "简体中文"};
let hsLanguage = "en";
try { hsLanguage = new URLSearchParams(location.search).get("lang") || localStorage.getItem("harnesssync-language") || "en"; } catch { /* storage can be disabled */ }
if (!Object.hasOwn(hsLanguages, hsLanguage)) hsLanguage = "en";
function hsT(message, values = {}) {
  const result = hsCatalogs[hsLanguage]?.[message.toLowerCase()] || message;
  return result.replace(/\{(\w+)\}/g, (match, key) => Object.hasOwn(values, key) ? String(values[key]) : match);
}
function hsApplyLanguage() {
  document.documentElement.lang = hsLanguage === "zh" ? "zh-Hans" : hsLanguage;
  for (const element of document.querySelectorAll("[data-i18n]")) element.textContent = hsT(element.dataset.i18n);
  try { localStorage.setItem("harnesssync-language", hsLanguage); } catch { /* optional preference */ }
}
const hsSelector = document.getElementById("language");
hsSelector.replaceChildren(...Object.entries(hsLanguages).map(([code, name]) => new Option(name, code)));
hsSelector.value = hsLanguage;
hsApplyLanguage();
