(function () {
  "use strict";

  /* ---------------------------------------------------------- colour scheme */

  /* The button steps through three choices: "system" follows the system's colour scheme,
     "light" and "dark" keep one. "system" is stored as no entry, so a reader who never
     clicks keeps following the system. From "system" the button goes to the other scheme
     and then to the system's scheme kept, so the first click always changes the colours. */
  var THEME_KEY = "theme";
  var THEME_STATES = {
    system: "Following the system's colour scheme",
    light: "Light colour scheme",
    dark: "Dark colour scheme"
  };
  var THEME_ACTIONS = {
    system: "Follow the system",
    light: "Switch to light",
    dark: "Switch to dark"
  };

  function nextThemeChoice(choice, systemIsDark) {
    var systemScheme = systemIsDark ? "dark" : "light";
    var otherScheme = systemIsDark ? "light" : "dark";
    if (choice === "system") return otherScheme;
    if (choice === otherScheme) return systemScheme;
    return "system";
  }

  function themeScheme(choice, systemIsDark) {
    if (choice === "system") return systemIsDark ? "dark" : "light";
    return choice;
  }

  function themeLabel(choice, systemIsDark) {
    return THEME_STATES[choice] + ". " + THEME_ACTIONS[nextThemeChoice(choice, systemIsDark)] + ".";
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      nextThemeChoice: nextThemeChoice,
      themeLabel: themeLabel,
      themeScheme: themeScheme
    };
  }
  if (typeof document === "undefined") return;

  var root = document.documentElement;
  var body = document.body;
  var base = root.getAttribute("data-root") || "./";

  var systemDark = window.matchMedia("(prefers-color-scheme: dark)");
  var toggle = document.querySelector(".theme-toggle");
  var themeChoice = root.getAttribute("data-theme-choice");
  if (themeChoice !== "light" && themeChoice !== "dark") themeChoice = "system";

  function applyThemeChoice() {
    root.setAttribute("data-theme-choice", themeChoice);
    root.setAttribute("data-theme", themeScheme(themeChoice, systemDark.matches));
    if (toggle) {
      var label = themeLabel(themeChoice, systemDark.matches);
      toggle.setAttribute("aria-label", label);
      toggle.title = label;
    }
  }

  applyThemeChoice();
  if (toggle) {
    toggle.addEventListener("click", function () {
      themeChoice = nextThemeChoice(themeChoice, systemDark.matches);
      try {
        if (themeChoice === "system") localStorage.removeItem(THEME_KEY);
        else localStorage.setItem(THEME_KEY, themeChoice);
      } catch (e) {}
      applyThemeChoice();
    });
  }
  /* A page left open follows the system when it changes, and the button's next step
     changes with it. */
  if (systemDark.addEventListener) systemDark.addEventListener("change", applyThemeChoice);

  /* ---------------------------------------------------------- phone sidebar */

  var menu = document.querySelector(".menu");
  var scrim = document.querySelector(".scrim");
  function setNav(open) {
    body.classList.toggle("nav-open", open);
    if (menu) menu.setAttribute("aria-expanded", String(open));
    if (scrim) scrim.hidden = !open;
  }
  if (menu) menu.addEventListener("click", function () { setNav(!body.classList.contains("nav-open")); });
  if (scrim) scrim.addEventListener("click", function () { setNav(false); });
  document.querySelectorAll(".sidebar a").forEach(function (a) {
    a.addEventListener("click", function () { setNav(false); });
  });

  /* -------------------------------------------------- active section marker */

  var sectionLinks = Array.prototype.slice.call(document.querySelectorAll('.toc-sections a[href^="#"]'));
  if (sectionLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    sectionLinks.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var headings = Object.keys(byId).map(function (id) { return document.getElementById(id); }).filter(Boolean);
    var current = null;
    function mark(id) {
      if (current) current.parentElement.classList.remove("active");
      current = byId[id] || null;
      if (current) current.parentElement.classList.add("active");
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) mark(entry.target.id);
      });
    }, { rootMargin: "-10% 0px -75% 0px" });
    headings.forEach(function (h) { observer.observe(h); });
  }

  /* ------------------------------------------------------------ linked tabs */

  /* Choosing a tab switches every set on the page with a tab of that label, and the next
     page opens the same way: the stored list holds labels in the order they were chosen,
     so replaying it leaves the latest choice in force for each set. */
  var TABS_KEY = "tabs";
  var TABS_KEPT = 10;
  var tabInputs = Array.prototype.slice.call(document.querySelectorAll(".tabbed-set > input"));

  function tabLabel(input) { return input.nextElementSibling.textContent.trim(); }

  function selectTabs(text) {
    tabInputs.forEach(function (input) {
      if (tabLabel(input) === text) input.checked = true;
    });
  }

  function chosenTabs() {
    var chosen = null;
    try { chosen = JSON.parse(localStorage.getItem(TABS_KEY)); } catch (e) {}
    return Array.isArray(chosen) ? chosen : [];
  }

  if (tabInputs.length) chosenTabs().forEach(selectTabs);

  tabInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      var text = tabLabel(input);
      var label = input.nextElementSibling;
      /* Sets above this one may change height, so the page moves by what the label
         moved, which keeps it under the pointer. */
      var top = label.getBoundingClientRect().top;
      selectTabs(text);
      var shift = label.getBoundingClientRect().top - top;
      if (Math.abs(shift) >= 1) window.scrollBy(0, shift);
      var chosen = chosenTabs().filter(function (other) { return other !== text; });
      chosen.push(text);
      try { localStorage.setItem(TABS_KEY, JSON.stringify(chosen.slice(-TABS_KEPT))); } catch (e) {}
    });
  });

  /* ---------------------------------------------- equation links on arrival */

  /* An equation's anchor exists only once MathJax has typeset the page. */
  if (/^#mjx-eqn/.test(window.location.hash) && window.MathJax && MathJax.startup) {
    MathJax.startup.promise.then(function () {
      var target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      if (target) target.scrollIntoView({ block: "start" });
    });
  }

  /* -------------------------------------------------------- copy permalinks */

  document.querySelectorAll("a.anchor").forEach(function (a) {
    a.addEventListener("click", function (e) {
      var url = new URL(a.getAttribute("href"), window.location.href).href;
      history.replaceState(null, "", url);
      var target = document.getElementById(a.getAttribute("href").slice(1));
      if (target) target.scrollIntoView({ block: "start" });
      e.preventDefault();
      var done = function () {
        a.classList.add("copied");
        setTimeout(function () { a.classList.remove("copied"); }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, done);
      } else {
        done();
      }
    });
  });

  /* ------------------------------------------------ enlarge figures, tables */

  var lightbox = document.createElement("div");
  lightbox.className = "lightbox";
  lightbox.hidden = true;
  lightbox.innerHTML =
    '<div class="lightbox-body" role="dialog" aria-modal="true" aria-label="Enlarged view">' +
    '<div class="lightbox-head"><button class="iconbtn lightbox-close" type="button" aria-label="Close">&#x2715;</button></div>' +
    '<div class="lightbox-content"></div></div>';
  document.body.appendChild(lightbox);
  var lightboxContent = lightbox.querySelector(".lightbox-content");
  var lightboxClose = lightbox.querySelector(".lightbox-close");
  var lastFocus = null;

  function openLightbox(figure) {
    var copy = figure.cloneNode(true);
    copy.removeAttribute("id");
    copy.querySelectorAll("a.anchor, .tool-group").forEach(function (el) { el.remove(); });
    lightboxContent.innerHTML = "";
    lightboxContent.appendChild(copy);
    lastFocus = document.activeElement;
    lightbox.hidden = false;
    body.classList.add("lightbox-open");
    lightboxClose.focus();
  }
  function closeLightbox() {
    if (lightbox.hidden) return;
    lightbox.hidden = true;
    body.classList.remove("lightbox-open");
    lightboxContent.innerHTML = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  /* The buttons keep off the text: a caption takes them at the end of its first line,
     with the text wrapping around them, and a table without one makes room in its header
     row. export.js adds its button to the same group. */
  function addToolGroup(figure) {
    var group = document.createElement("div");
    var caption = figure.querySelector("figcaption");
    group.className = "tool-group";
    figure.classList.add("tool-host");
    if (caption) {
      group.classList.add("tool-inline");
      caption.insertBefore(group, caption.firstChild);
    } else {
      group.classList.add("tool-right");
      figure.classList.add("tool-uncaptioned");
      figure.appendChild(group);
    }
    return group;
  }

  function enlargeButton(figure) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "tool-toggle iconbtn";
    button.title = "Enlarge";
    button.setAttribute("aria-label", "Enlarge " + (figure.matches(".table") ? "table" : "figure"));
    button.innerHTML =
      '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
      '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" fill="none" stroke="currentColor" ' +
      'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    button.addEventListener("click", function () { openLightbox(figure); });
    return button;
  }

  var enlargesTables = document.body.getAttribute("data-enlarge-tables") !== "false";
  document.querySelectorAll("figure").forEach(function (figure) {
    if (!figure.querySelector("svg, img, .table-wrap")) return;
    var group = addToolGroup(figure);
    if (enlargesTables || !figure.matches(".table")) group.appendChild(enlargeButton(figure));
  });
  lightboxClose.addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", function (e) { if (e.target === lightbox) closeLightbox(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeLightbox(); });

  /* ----------------------------------------------------------------- search */

  var overlay = document.querySelector(".search");
  var input = document.querySelector(".search-input");
  var results = document.querySelector(".search-results");
  var index = null;
  var selected = -1;

  function openSearch() {
    if (!overlay) return;
    overlay.hidden = false;
    input.value = "";
    results.innerHTML = "";
    selected = -1;
    input.focus();
    if (!index) {
      fetch(base + "search.json").then(function (r) { return r.json(); }).then(function (data) {
        index = data.map(function (entry) {
          entry.haystack = (entry.page + " " + entry.section + " " + entry.text).toLowerCase();
          return entry;
        });
      }).catch(function () { index = []; });
    }
  }
  function closeSearch() { if (overlay) overlay.hidden = true; }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }

  function snippet(text, terms) {
    var lower = text.toLowerCase();
    var at = -1;
    terms.forEach(function (t) { var i = lower.indexOf(t); if (i >= 0 && (at < 0 || i < at)) at = i; });
    var start = Math.max(0, at - 70);
    var end = Math.min(text.length, (at < 0 ? 0 : at) + 150);
    var out = (start > 0 ? "…" : "") + escapeHtml(text.slice(start, end)) + (end < text.length ? "…" : "");
    terms.forEach(function (t) {
      out = out.replace(new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"), "<mark>$1</mark>");
    });
    return out;
  }

  function runSearch() {
    if (!index) return;
    var terms = input.value.toLowerCase().split(/\s+/).filter(function (t) { return t.length > 1; });
    results.innerHTML = "";
    selected = -1;
    if (!terms.length) return;
    var scored = [];
    index.forEach(function (entry) {
      var score = 0;
      for (var i = 0; i < terms.length; i++) {
        var t = terms[i];
        if (entry.haystack.indexOf(t) < 0) return;
        score += 1;
        if (entry.section.toLowerCase().indexOf(t) >= 0) score += 3;
        if (entry.page.toLowerCase().indexOf(t) >= 0) score += 2;
      }
      scored.push({ entry: entry, score: score });
    });
    scored.sort(function (a, b) { return b.score - a.score; });
    if (!scored.length) {
      results.innerHTML = '<li class="search-empty">No matches.</li>';
      return;
    }
    scored.slice(0, 12).forEach(function (hit) {
      var e = hit.entry;
      var li = document.createElement("li");
      li.innerHTML =
        '<a href="' + base + e.url + '">' +
        '<span class="search-crumb">' + escapeHtml(e.page) + '</span>' +
        '<span class="search-title">' + escapeHtml(e.section || e.page) + '</span>' +
        '<span class="search-snippet">' + snippet(e.text, terms) + '</span></a>';
      results.appendChild(li);
    });
  }

  function moveSelection(delta) {
    var items = results.querySelectorAll("li");
    if (!items.length) return;
    if (selected >= 0) items[selected].classList.remove("selected");
    selected = (selected + delta + items.length) % items.length;
    items[selected].classList.add("selected");
    items[selected].scrollIntoView({ block: "nearest" });
  }

  if (overlay) {
    document.querySelectorAll(".search-open").forEach(function (b) { b.addEventListener("click", openSearch); });
    document.querySelector(".search-close").addEventListener("click", closeSearch);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) closeSearch(); });
    input.addEventListener("input", runSearch);
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); moveSelection(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveSelection(-1); }
      else if (e.key === "Enter") {
        var item = results.querySelector("li.selected a") || results.querySelector("li a");
        if (item) window.location.href = item.getAttribute("href");
      }
    });
    document.addEventListener("keydown", function (e) {
      var typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
      if (e.key === "Escape" && !overlay.hidden) closeSearch();
      else if (e.key === "/" && !typing && overlay.hidden) { e.preventDefault(); openSearch(); }
      else if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); overlay.hidden ? openSearch() : closeSearch(); }
    });
  }
})();
