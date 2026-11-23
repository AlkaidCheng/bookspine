/* Display equations that fit the window. A page writes its equations for the full text
   column. On a narrow screen an equation breaks at its marks, macros that have a second
   definition there, and one still wider than its box is drawn smaller, down to MIN_SCALE
   of its size. Below that it scrolls, as every equation would without this script.

   The script takes part in MathJax's start, so its tag stands before MathJax's and
   carries the narrow definitions as JSON in data-narrow-macros. */
(function () {
  "use strict";

  /* A window up to this width is a narrow screen. A window of at most 52rem leaves the
     text column its width less 2rem of padding (book.css), so here a formula that fills
     the 47rem of --measure would be drawn at three quarters of its size, close to
     MIN_SCALE. A phone held upright is narrower, where breaking the formula keeps it
     larger than shrinking it would. */
  var NARROW_QUERY = "(max-width: 37.5rem)";

  /* The smallest an equation is drawn, as a fraction of its size. A subscript is 0.71 of
     its base, and MathJax draws none smaller than 8px:
     https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/core/MmlTree/MmlNodes/math.ts
     At 0.7 the subscripts of an equation in the theme's 17px text are still 9px. */
  var MIN_SCALE = 0.7;

  /* A hair under the exact ratio, so that rounding leaves no pixel to scroll. */
  var FIT_MARGIN = 0.995;

  /* How long the window must keep a size before the equations are fitted again. */
  var RESIZE_DELAY_MS = 150;

  /* The fraction of its size at which content `contentWidth` wide fits a box `boxWidth`
     wide, no less than MIN_SCALE. */
  function fitScale(boxWidth, contentWidth) {
    if (contentWidth <= boxWidth) return 1;
    return Math.max(MIN_SCALE, (boxWidth / contentWidth) * FIT_MARGIN);
  }

  /* TeX that gives each macro of `macros`, which take no arguments, its definition. */
  function redefinitions(macros) {
    return Object.keys(macros).map(function (name) {
      return "\\renewcommand{\\" + name + "}{" + macros[name] + "}";
    }).join("");
  }

  function usesMacro(tex, names) {
    return names.some(function (name) {
      return new RegExp("\\\\" + name + "(?![A-Za-z])").test(tex);
    });
  }

  /* `names`, and the macros of `macros` whose definitions lead to one of them, as a
     book's shorter name for a mark does. */
  function macrosReaching(macros, names) {
    var reaching = names.slice();
    var grew = true;
    while (grew) {
      grew = false;
      Object.keys(macros).forEach(function (name) {
        var definition = Array.isArray(macros[name]) ? macros[name][0] : macros[name];
        if (reaching.indexOf(name) < 0 && usesMacro(definition, reaching)) {
          reaching.push(name);
          grew = true;
        }
      });
    }
    return reaching;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      FIT_MARGIN: FIT_MARGIN,
      MIN_SCALE: MIN_SCALE,
      fitScale: fitScale,
      macrosReaching: macrosReaching,
      redefinitions: redefinitions,
      usesMacro: usesMacro
    };
  }
  if (typeof document === "undefined") return;

  var config = window.MathJax;
  var script = document.currentScript;
  if (!config || !config.tex || !script) return;

  /* The configuration keeps the wide definitions, which an exported equation states. */
  var configMacros = config.tex.macros || {};
  var narrowMacros = JSON.parse(script.getAttribute("data-narrow-macros") || "{}");
  var wideMacros = {};
  Object.keys(narrowMacros).forEach(function (name) { wideMacros[name] = configMacros[name]; });
  var narrowScreen = window.matchMedia(NARROW_QUERY);

  /* A definition made in one formula holds for the rest of the page:
     https://docs.mathjax.org/en/v3.2/input/tex/macros.html
     The formula is inline, because a display would take an equation number. */
  function defineForScreen() {
    var macros = narrowScreen.matches ? narrowMacros : wideMacros;
    window.MathJax.tex2mml(redefinitions(macros), { display: false });
  }

  function equationBoxes() {
    return Array.prototype.slice.call(document.querySelectorAll("div.arithmatex"));
  }

  /* Every box returns to full size before any is measured, so the page is laid out once
     for all of them. An equation in a closed box or an unchosen tab has no width. */
  function fitEquations() {
    var boxes = equationBoxes();
    boxes.forEach(function (box) { box.style.fontSize = ""; });
    var scales = boxes.map(function (box) { return fitScale(box.clientWidth, box.scrollWidth); });
    boxes.forEach(function (box, index) {
      if (scales[index] < 1) box.style.fontSize = (scales[index] * 100).toFixed(2) + "%";
    });
  }

  /* Typesetting again changes the height of the equations above the reader's place. The
     first equation that starts inside the window, or else the page's foot, is put back
     where it was. */
  function holdPlace() {
    var marks = equationBoxes().concat(document.querySelector(".colophon") || []);
    var mark = marks.filter(function (element) {
      return element.getClientRects().length && element.getBoundingClientRect().top >= 0;
    })[0];
    var top = mark && mark.getBoundingClientRect().top;
    return function () {
      if (mark) window.scrollBy(0, mark.getBoundingClientRect().top - top);
    };
  }

  /* MathJax reads a macro when it compiles a formula, so the page is typeset again from
     its TeX, as "Updating Previously Typeset Content" describes:
     https://docs.mathjax.org/en/v3.2/web/typeset.html
     The equations keep their boxes, and with them their export menus, and take the
     same numbers and anchors. */
  function typesetAgain() {
    var restorePlace = holdPlace();
    defineForScreen();
    window.MathJax.startup.document.state(0);
    window.MathJax.texReset();
    return window.MathJax.typesetPromise().then(function () {
      fitEquations();
      restorePlace();
    });
  }

  function pageUsesMarks() {
    var names = macrosReaching(configMacros, Object.keys(narrowMacros));
    return Array.from(window.MathJax.startup.document.math).some(function (item) {
      return usesMacro(item.math, names);
    });
  }

  function watchWindow() {
    fitEquations();
    var fittedWidth = window.innerWidth;
    var timer = null;
    /* A phone resizes its window in height alone as its address bar comes and goes. */
    window.addEventListener("resize", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        if (window.innerWidth === fittedWidth) return;
        fittedWidth = window.innerWidth;
        fitEquations();
      }, RESIZE_DELAY_MS);
    });
    /* A box that opens and a tab that is chosen show equations not yet measured. The
       toggle event does not bubble. */
    document.addEventListener("toggle", fitEquations, true);
    document.addEventListener("change", function (event) {
      if (event.target.matches(".tabbed-set > input")) fitEquations();
    });
    /* A page without marks reads the same on both screens. */
    if (!pageUsesMarks() || !narrowScreen.addEventListener) return;
    var typeset = Promise.resolve();
    narrowScreen.addEventListener("change", function () {
      typeset = typeset.then(typesetAgain);
    });
  }

  /* pageReady runs once MathJax is loaded and typesets the page:
     https://docs.mathjax.org/en/v3.2/options/startup/startup.html */
  var startup = config.startup = config.startup || {};
  var pageReady = startup.pageReady;
  startup.pageReady = function () {
    if (narrowScreen.matches) defineForScreen();
    var typeset = pageReady ? pageReady() : window.MathJax.startup.defaultPageReady();
    return Promise.resolve(typeset).then(watchWindow);
  };
})();
