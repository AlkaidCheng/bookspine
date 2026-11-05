/* Export menus: a button on each table, figure, code block and display equation opens a
   menu of file formats. Text formats are read from the page, PNG is drawn on a
   canvas with the page's own fonts, and PDF goes through the browser's print dialog,
   which keeps vectors and fonts. Exports always use the light colour scheme. */
(function () {
  "use strict";

  /* A PNG is drawn at three times the page's size, and held below the canvas limits at
     https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/canvas#maximum_canvas_size */
  var PNG_SCALE = 3;
  var MAX_CANVAS_SIDE = 8192;

  var BACKGROUND = "#ffffff";
  var FLASH_MILLISECONDS = 1400;

  /* The characters LaTeX treats as commands: https://ctan.org/pkg/lshort */
  var LATEX_SPECIALS = {
    "\\": "\\textbackslash{}",
    "&": "\\&",
    "%": "\\%",
    "$": "\\$",
    "#": "\\#",
    "_": "\\_",
    "{": "\\{",
    "}": "\\}",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}"
  };
  var LATEX_COLUMNS = { left: "l", center: "c", right: "r" };

  /* Environments that number themselves, so an exported equation needs no wrapper. */
  var LATEX_DISPLAY_START = /^\s*\\begin\{(equation|align|alignat|gather|multline|flalign|eqnarray)\*?\}/;

  /* Column markers of a GitHub Flavored Markdown table: https://github.github.com/gfm/#tables-extension- */
  var MARKDOWN_COLUMNS = { left: ":---", center: ":---:", right: "---:" };

  /* ----------------------------------------------------------- text formats */

  /* A table is { header, rows, align, caption }. A cell is a list of runs, and a run is
     { text, bold, italic, code, math, href }. */

  function plainRun(run) { return run.math ? "$" + run.text + "$" : run.text; }
  function plainCell(runs) { return runs.map(plainRun).join("").trim(); }

  /* Quoting and line endings follow https://www.rfc-editor.org/rfc/rfc4180 */
  function csvField(text) {
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  function toCsv(table) {
    return [table.header].concat(table.rows).map(function (row) {
      return row.map(function (cell) { return csvField(plainCell(cell)); }).join(",");
    }).join("\r\n") + "\r\n";
  }

  /* Keep the spaces around a run outside its emphasis marks. */
  function wrapText(text, mark) {
    var parts = /^(\s*)(.*?)(\s*)$/.exec(text);
    return parts[2] ? parts[1] + mark + parts[2] + mark + parts[3] : text;
  }

  function markdownCode(text) {
    var escaped = text.replace(/\|/g, "\\|");
    return text.indexOf("`") < 0 ? "`" + escaped + "`" : "`` " + escaped + " ``";
  }

  function markdownRun(run) {
    if (run.math) return "$" + run.text.replace(/\|/g, "\\|") + "$";
    var text = run.code ? markdownCode(run.text) : run.text.replace(/[\\|*`]/g, "\\$&");
    var mark = (run.bold ? "**" : "") + (run.italic ? "*" : "");
    if (mark) text = wrapText(text, mark);
    return run.href ? "[" + text + "](" + run.href + ")" : text;
  }

  function markdownCell(runs) { return runs.map(markdownRun).join("").trim(); }
  function markdownRow(cells) { return "| " + cells.join(" | ") + " |"; }

  function toMarkdown(table) {
    var lines = [
      markdownRow(table.header.map(markdownCell)),
      markdownRow(table.align.map(function (align) { return MARKDOWN_COLUMNS[align] || "---"; }))
    ];
    table.rows.forEach(function (row) { lines.push(markdownRow(row.map(markdownCell))); });
    var caption = table.caption ? "\nTable: " + markdownCell(table.caption) + "\n" : "";
    return lines.join("\n") + "\n" + caption;
  }

  function escapeLatex(text) {
    return text.replace(/[\\&%$#_{}~^]/g, function (character) { return LATEX_SPECIALS[character]; });
  }

  function latexRun(run) {
    if (run.math) return "$" + run.text + "$";
    var text = escapeLatex(run.text);
    if (run.code) text = "\\texttt{" + text + "}";
    if (run.bold) text = "\\textbf{" + text + "}";
    if (run.italic) text = "\\emph{" + text + "}";
    return run.href ? "\\href{" + run.href.replace(/[%#]/g, "\\$&") + "}{" + text + "}" : text;
  }

  function latexCell(runs) { return runs.map(latexRun).join("").trim(); }
  function latexRow(cells) { return "    " + cells.map(latexCell).join(" & ") + " \\\\"; }

  /* Definitions of the book's macros that `source` uses. A macro may replace a command
     LaTeX already has, as \vec does here, so \providecommand alone would not do. */
  function macroDefinitions(source, macros) {
    return Object.keys(macros || {}).filter(function (name) {
      return new RegExp("\\\\" + name + "(?![A-Za-z])").test(source);
    }).map(function (name) {
      var definition = macros[name];
      var body = Array.isArray(definition) ? "[" + definition[1] + "]{" + definition[0] + "}" : "{" + definition + "}";
      return "\\providecommand{\\" + name + "}{}\\renewcommand{\\" + name + "}" + body;
    });
  }

  function hasLink(table) {
    return [table.header].concat(table.rows).some(function (row) {
      return row.some(function (cell) {
        return cell.some(function (run) { return run.href; });
      });
    });
  }

  function toLatex(table, macros) {
    var packages = ["booktabs"].concat(hasLink(table) ? ["hyperref"] : []);
    var columns = table.align.map(function (align) { return LATEX_COLUMNS[align] || "l"; }).join("");
    var body = [
      "\\begin{table}",
      "  \\centering",
      table.caption ? "  \\caption{" + latexCell(table.caption) + "}" : null,
      "  \\begin{tabular}{" + columns + "}",
      "    \\toprule",
      latexRow(table.header),
      "    \\midrule"
    ].concat(table.rows.map(latexRow), ["    \\bottomrule", "  \\end{tabular}", "\\end{table}"]);
    var text = body.filter(function (line) { return line !== null; }).join("\n");
    var preamble = packages.map(function (name) { return "% Needs \\usepackage{" + name + "}"; });
    return preamble.concat(macroDefinitions(text, macros), [text]).join("\n") + "\n";
  }

  function equationLatex(tex, macros) {
    var body = LATEX_DISPLAY_START.test(tex) ? tex : "\\begin{equation}\n" + tex + "\n\\end{equation}";
    return macroDefinitions(tex, macros).concat([body]).join("\n") + "\n";
  }

  /* Replace CSS variables by values, for programs that do not read them. */
  function resolveVariables(source, valueOf) {
    return source.replace(/var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)/g, function (whole, name, fallback) {
      return valueOf(name) || (fallback || "").trim() || whole;
    });
  }

  function slug(text) {
    return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }

  var formats = {
    equationLatex: equationLatex,
    macroDefinitions: macroDefinitions,
    resolveVariables: resolveVariables,
    slug: slug,
    toCsv: toCsv,
    toLatex: toLatex,
    toMarkdown: toMarkdown
  };

  if (typeof module !== "undefined" && module.exports) module.exports = formats;
  if (typeof document === "undefined") return;

  var root = document.documentElement;

  function iconHtml(path) {
    return (
      '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="' + path +
      '" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    );
  }
  var icons = {
    save: iconHtml("M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 20h14"),
    copy: iconHtml("M9 9h11v11H9zM15 9V4H4v11h5"),
    done: iconHtml("M5 12.5l4.5 4.5L19 7.5"),
    failed: iconHtml("M6 6l12 12M18 6L6 18")
  };

  /* ---------------------------------------------------- reading the page */

  /* The TeX of every formula in `element`, by its typeset container. */
  function mathSources(element) {
    var sources = new Map();
    var mathDocument = window.MathJax && MathJax.startup && MathJax.startup.document;
    if (mathDocument && mathDocument.getMathItemsWithin) {
      mathDocument.getMathItemsWithin(element).forEach(function (item) {
        sources.set(item.typesetRoot, item.math);
      });
    }
    return sources;
  }

  function texOf(element, sources) {
    var container = element.querySelector("mjx-container");
    if (container && sources.has(container)) return sources.get(container).trim();
    return element.textContent.replace(/^\s*\\[(\[]\s*|\s*\\[)\]]\s*$/g, "").trim();
  }

  function macros() {
    return (window.MathJax && MathJax.config && MathJax.config.tex && MathJax.config.tex.macros) || {};
  }

  function readRuns(node, sources, style, runs) {
    node.childNodes.forEach(function (child) {
      if (child.nodeType === Node.TEXT_NODE) {
        var text = child.nodeValue.replace(/\s+/g, " ");
        if (text) runs.push(Object.assign({}, style, { text: text }));
        return;
      }
      if (child.nodeType !== Node.ELEMENT_NODE || child.matches(".caplabel, .anchor, .tool-group")) return;
      if (child.matches(".arithmatex")) {
        runs.push({ text: texOf(child, sources), math: true });
        return;
      }
      var inner = Object.assign({}, style);
      if (child.matches("strong, b")) inner.bold = true;
      if (child.matches("em, i")) inner.italic = true;
      if (child.matches("code")) inner.code = true;
      if (child.matches("a[href]")) inner.href = child.href;
      readRuns(child, sources, inner, runs);
    });
    return runs;
  }

  function readTable(figure) {
    var sources = mathSources(figure);
    function cellRuns(cell) { return readRuns(cell, sources, {}, []); }
    function rowCells(row) { return Array.prototype.map.call(row.cells, cellRuns); }
    var element = figure.querySelector("table");
    var rows = Array.prototype.slice.call(element.rows);
    var header = rows.shift();
    var caption = figure.querySelector("figcaption");
    return {
      header: rowCells(header),
      align: Array.prototype.map.call(header.cells, function (cell) { return cell.style.textAlign; }),
      rows: rows.map(rowCells),
      caption: caption ? cellRuns(caption) : null
    };
  }

  function equationTex(element) { return texOf(element, mathSources(element)); }

  /* --------------------------------------------------------- staging */

  /* Show computed colours as the light scheme has them; returns the way back. */
  function useLightTheme() {
    var theme = root.getAttribute("data-theme");
    root.setAttribute("data-theme", "light");
    return function () { root.setAttribute("data-theme", theme); };
  }

  /* An off-page copy of the component, free of the page's scrolling and width. */
  function stageComponent(component) {
    var target = component.target;
    var stage = document.createElement("div");
    stage.className = "export-stage prose";
    var holder = document.createElement(component.kind === "figure" ? "figure" : "div");
    var copy = target.cloneNode(true);
    copy.removeAttribute("tabindex");
    holder.appendChild(copy);
    stage.appendChild(holder);
    var width = Math.max(target.getBoundingClientRect().width, target.scrollWidth) + "px";
    if (component.kind === "code") {
      // A code block keeps its source's lines, however it wraps on the page.
      stage.style.width = "max-content";
      stage.style.minWidth = width;
    } else {
      stage.style.width = width;
    }
    document.body.appendChild(stage);
    return stage;
  }

  /* ---------------------------------------------------------- SVG source */

  function svgSource(svg, keepText) {
    var copy = svg.cloneNode(true);
    ["class", "role", "tabindex", "aria-label"].forEach(function (name) { copy.removeAttribute(name); });
    var box = svg.viewBox.baseVal;
    copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    copy.setAttribute("width", box.width);
    copy.setAttribute("height", box.height);
    if (!keepText) copy.querySelectorAll("text").forEach(function (text) { text.remove(); });

    var restoreTheme = useLightTheme();
    var svgStyle = getComputedStyle(svg);
    copy.setAttribute("font-family", svgStyle.fontFamily);
    copy.setAttribute("color", svgStyle.color);
    var rootStyle = getComputedStyle(root);
    var source = resolveVariables(new XMLSerializer().serializeToString(copy), function (name) {
      return rootStyle.getPropertyValue(name).trim();
    });
    restoreTheme();
    return source;
  }

  /* An image of an SVG without its text: an SVG drawn as an image cannot reach the
     page's fonts, so paintSvg writes the text on the canvas. */
  function loadSvgImage(svg) {
    return new Promise(function (resolve, reject) {
      var image = new Image();
      image.onload = function () { resolve(image); };
      image.onerror = function () { reject(new Error("The figure could not be read")); };
      image.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgSource(svg, false));
    });
  }

  /* ---------------------------------------------------------- painting */

  function canvasFont(style) {
    return [style.fontStyle, style.fontWeight, style.fontSize, style.fontFamily].join(" ");
  }

  function isVisibleColour(colour) {
    return colour !== "transparent" && !/^rgba\(.*,\s*0\)$/.test(colour);
  }

  function setTextStyle(context, style, colour) {
    context.font = canvasFont(style);
    context.fillStyle = colour;
    if ("letterSpacing" in context) {
      context.letterSpacing = style.letterSpacing === "normal" ? "0px" : style.letterSpacing;
    }
  }

  function transformedText(text, style) {
    if (style.textTransform === "uppercase") return text.toUpperCase();
    if (style.textTransform === "lowercase") return text.toLowerCase();
    return text;
  }

  function textRect(range, node, start, end) {
    range.setStart(node, start);
    range.setEnd(node, end);
    return range.getClientRects();
  }

  /* The parts of a word on each line it occupies, as a hyphenated word can have two. */
  function wordParts(range, node, start, end) {
    if (textRect(range, node, start, end).length < 2) return [[start, end]];
    var parts = [];
    var partStart = start;
    var top = null;
    for (var index = start; index < end; index++) {
      var rect = textRect(range, node, index, index + 1)[0];
      if (!rect) continue;
      if (top !== null && Math.abs(rect.top - top) > 1) {
        parts.push([partStart, index]);
        partStart = index;
      }
      top = rect.top;
    }
    parts.push([partStart, end]);
    return parts;
  }

  /* Each word is drawn where the browser placed it, so the lines break as on the page.
     A canvas cannot turn ligatures off, so text without them goes character by character. */
  function paintText(context, node, style, origin) {
    var pieces = style.fontVariantLigatures === "none" ? /\S/gu : /\S+/g;
    var range = document.createRange();
    var match;
    setTextStyle(context, style, style.color);
    while ((match = pieces.exec(node.nodeValue))) {
      wordParts(range, node, match.index, match.index + match[0].length).forEach(function (part) {
        var rect = textRect(range, node, part[0], part[1])[0];
        if (!rect) return;
        var word = transformedText(node.nodeValue.slice(part[0], part[1]), style);
        var ascent = context.measureText(word).fontBoundingBoxAscent;
        context.fillText(word, rect.left - origin.x, rect.top - origin.y + ascent);
      });
    }
  }

  /* MathJax's CHTML output keeps each glyph in a ::before of an mjx-c element, whose top
     padding is the glyph's height above the baseline. */
  function paintGlyph(context, element, style, origin) {
    var glyph = getComputedStyle(element, "::before");
    var character = glyph.content.replace(/^"|"$/g, "");
    if (!character || character === "none") return;
    var rect = element.getBoundingClientRect();
    setTextStyle(context, style, style.color);
    context.fillText(character, rect.left - origin.x, rect.top - origin.y + parseFloat(glyph.paddingTop));
  }

  function paintBorders(context, style, rect, origin) {
    var x = rect.left - origin.x;
    var y = rect.top - origin.y;
    var top = parseFloat(style.borderTopWidth);
    var right = parseFloat(style.borderRightWidth);
    var bottom = parseFloat(style.borderBottomWidth);
    var left = parseFloat(style.borderLeftWidth);
    if (top && style.borderTopStyle !== "none") {
      context.fillStyle = style.borderTopColor;
      context.fillRect(x, y, rect.width, top);
    }
    if (bottom && style.borderBottomStyle !== "none") {
      context.fillStyle = style.borderBottomColor;
      context.fillRect(x, y + rect.height - bottom, rect.width, bottom);
    }
    if (left && style.borderLeftStyle !== "none") {
      context.fillStyle = style.borderLeftColor;
      context.fillRect(x, y, left, rect.height);
    }
    if (right && style.borderRightStyle !== "none") {
      context.fillStyle = style.borderRightColor;
      context.fillRect(x + rect.width - right, y, right, rect.height);
    }
  }

  function paintBox(context, element, style, origin) {
    Array.prototype.forEach.call(element.getClientRects(), function (rect) {
      if (isVisibleColour(style.backgroundColor)) {
        context.fillStyle = style.backgroundColor;
        context.fillRect(rect.left - origin.x, rect.top - origin.y, rect.width, rect.height);
      }
      paintBorders(context, style, rect, origin);
    });
  }

  function paintElement(context, element, origin) {
    var style = getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden") return;
    if (element.matches("mjx-assistive-mml")) return;
    paintBox(context, element, style, origin);
    if (element.matches("mjx-c")) {
      paintGlyph(context, element, style, origin);
      return;
    }
    if (element.matches("img")) {
      var rect = element.getBoundingClientRect();
      if (element.naturalWidth) {
        context.drawImage(element, rect.left - origin.x, rect.top - origin.y, rect.width, rect.height);
      }
      return;
    }
    element.childNodes.forEach(function (child) {
      if (child.nodeType === Node.TEXT_NODE) paintText(context, child, style, origin);
      else if (child.nodeType === Node.ELEMENT_NODE) paintElement(context, child, origin);
    });
  }

  function paintSvg(context, svg, image, origin) {
    var rect = svg.getBoundingClientRect();
    context.drawImage(image, rect.left - origin.x, rect.top - origin.y, rect.width, rect.height);
    svg.querySelectorAll("text").forEach(function (text) {
      if (!text.getNumberOfChars()) return;
      var style = getComputedStyle(text);
      var start = text.getStartPositionOfChar(0);
      var matrix = text.getScreenCTM();
      context.save();
      context.translate(-origin.x, -origin.y);
      context.transform(matrix.a, matrix.b, matrix.c, matrix.d, matrix.e, matrix.f);
      setTextStyle(context, style, style.fill);
      context.fillText(text.textContent.replace(/\s+/g, " ").trim(), start.x, start.y);
      context.restore();
    });
  }

  function paintStage(stage, image) {
    var box = stage.getBoundingClientRect();
    var scale = Math.min(PNG_SCALE, MAX_CANVAS_SIDE / Math.max(box.width, box.height));
    var canvas = document.createElement("canvas");
    canvas.width = Math.ceil(box.width * scale);
    canvas.height = Math.ceil(box.height * scale);
    var context = canvas.getContext("2d");
    context.scale(scale, scale);
    context.fillStyle = BACKGROUND;
    context.fillRect(0, 0, box.width, box.height);
    var origin = { x: box.left, y: box.top };
    if (image) paintSvg(context, stage.querySelector("svg"), image, origin);
    else paintElement(context, stage, origin);
    return canvas;
  }

  function canvasBlob(canvas) {
    return new Promise(function (resolve, reject) {
      canvas.toBlob(function (blob) {
        if (blob) resolve(blob);
        else reject(new Error("The image could not be written"));
      }, "image/png");
    });
  }

  /* ---------------------------------------------------------- exporting */

  function save(name, blob) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function imagesDecoded(stage) {
    return Promise.all(Array.prototype.map.call(stage.querySelectorAll("img"), function (image) {
      return image.decode();
    }));
  }

  function pngBlob(component) {
    var isSvg = component.target.matches("svg");
    return document.fonts.ready.then(function () {
      return isSvg ? loadSvgImage(component.target) : null;
    }).then(function (image) {
      var restoreTheme = useLightTheme();
      var stage = stageComponent(component);
      return imagesDecoded(stage).then(function () {
        return paintStage(stage, image);
      }).finally(function () {
        stage.remove();
        restoreTheme();
      });
    }).then(canvasBlob);
  }

  function exportPng(component, name) {
    return pngBlob(component).then(function (blob) { save(name + ".png", blob); });
  }

  /* The clipboard API exists only on https and localhost. */
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text);
    return Promise.reject(new Error("This page cannot use the clipboard"));
  }

  /* Safari keeps the click's permission only for a ClipboardItem made at once, so the
     item takes the promise of the image rather than the image. */
  function copyPng(component) {
    if (!navigator.clipboard || !navigator.clipboard.write || !window.ClipboardItem) {
      return Promise.reject(new Error("This page cannot copy images"));
    }
    return navigator.clipboard.write([new ClipboardItem({ "image/png": pngBlob(component) })]);
  }

  /* The print dialog keeps vectors and fonts, which no script in the page can match
     without a PDF library. @page sizes the sheet to the component; a browser that
     ignores it prints on its default paper. The file name comes from the title. */
  function exportPdf(component, name) {
    var restoreTheme = useLightTheme();
    var stage = stageComponent(component);
    var box = stage.getBoundingClientRect();
    var pageStyle = document.createElement("style");
    var width = Math.ceil(box.width);
    var height = Math.ceil(box.height);
    pageStyle.textContent =
      "@page { size: " + width + "px " + height + "px; margin: 0; }" +
      "@media print { .export-stage { box-sizing: border-box; height: " + height + "px; overflow: hidden; } }";
    document.head.appendChild(pageStyle);
    var title = document.title;
    document.title = name;
    root.classList.add("export-printing");
    window.addEventListener("afterprint", function () {
      root.classList.remove("export-printing");
      document.title = title;
      pageStyle.remove();
      stage.remove();
      restoreTheme();
    }, { once: true });
    window.print();
    return Promise.resolve();
  }

  function textFormat(label, extension, read) {
    return {
      label: label,
      save: function (component, name) {
        var type = "text/plain;charset=utf-8";
        save(name + "." + extension, new Blob([read(component)], { type: type }));
        return Promise.resolve();
      },
      copy: function (component) { return copyText(read(component)); }
    };
  }

  var imageFormats = [
    { label: "PNG", save: exportPng, copy: copyPng },
    { label: "PDF", save: exportPdf, hint: "Save as PDF, through the print dialog" }
  ];

  function tableFormats() {
    return [
      textFormat("Markdown", "md", function (component) { return toMarkdown(readTable(component.host)); }),
      textFormat("CSV", "csv", function (component) { return toCsv(readTable(component.host)); }),
      textFormat("LaTeX", "tex", function (component) { return toLatex(readTable(component.host), macros()); })
    ].concat(imageFormats);
  }

  function svgFormats() {
    var format = textFormat("SVG", "svg", function (component) { return svgSource(component.target, true); });
    return [format].concat(imageFormats);
  }

  function equationFormats() {
    var format = textFormat("LaTeX", "tex", function (component) {
      return equationLatex(equationTex(component.target), macros());
    });
    return [format].concat(imageFormats);
  }

  /* -------------------------------------------------------------- the menu */

  var menu = document.createElement("div");
  menu.className = "export-menu";
  menu.setAttribute("role", "menu");
  menu.hidden = true;
  document.body.appendChild(menu);
  var openToggle = null;

  function closeMenu() {
    if (menu.hidden) return;
    menu.hidden = true;
    openToggle.setAttribute("aria-expanded", "false");
    openToggle.focus();
    openToggle = null;
  }

  /* Show the outcome of an action on its button for a moment. */
  function flash(button, icon, message) {
    var holder = button.querySelector(".export-icon");
    var label = button.getAttribute("aria-label");
    var shown = holder.innerHTML;
    holder.innerHTML = icon;
    button.setAttribute("aria-label", message);
    button.title = message;
    setTimeout(function () {
      holder.innerHTML = shown;
      button.setAttribute("aria-label", label);
      button.title = label;
    }, FLASH_MILLISECONDS);
  }

  function menuButton(className, label, icon) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.title = label;
    button.setAttribute("role", "menuitem");
    button.setAttribute("aria-label", label);
    button.innerHTML = '<span class="export-icon">' + icon + "</span>";
    return button;
  }

  function saveButton(component, format) {
    var button = menuButton("export-save", format.hint || "Save as " + format.label, icons.save);
    var name = document.createElement("span");
    name.className = "export-name";
    name.textContent = format.label;
    button.insertBefore(name, button.firstChild);
    button.addEventListener("click", function () {
      format.save(component, component.name).then(closeMenu).catch(function (error) {
        console.error(error);
        flash(button, icons.failed, "Could not save");
      });
    });
    return button;
  }

  function copyButton(component, format) {
    var button = menuButton("export-copy", "Copy as " + format.label, icons.copy);
    button.addEventListener("click", function () {
      format.copy(component).then(function () {
        flash(button, icons.done, "Copied");
      }).catch(function (error) {
        console.error(error);
        flash(button, icons.failed, "Could not copy");
      });
    });
    return button;
  }

  /* The save button spans the row, so that the whole row saves, and the copy button
     sits on top of it in a column of its own. */
  function menuRow(component, format) {
    var row = document.createElement("div");
    row.className = "export-row";
    row.setAttribute("role", "none");
    row.appendChild(saveButton(component, format));
    if (format.copy) row.appendChild(copyButton(component, format));
    return row;
  }

  function menuHeading() {
    var heading = document.createElement("div");
    heading.className = "export-heading";
    heading.setAttribute("aria-hidden", "true");
    heading.innerHTML = "<span>Format</span><span>Copy</span><span>Save</span>";
    return heading;
  }

  /* Below the button, or above it when the menu would run off the window. */
  function placeMenu(toggle) {
    var rect = toggle.getBoundingClientRect();
    var margin = 8;
    var gap = 4;
    var left = Math.min(rect.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - margin);
    var top = rect.bottom + gap;
    if (top + menu.offsetHeight > window.innerHeight - margin) {
      top = Math.max(margin, rect.top - gap - menu.offsetHeight);
    }
    menu.style.left = Math.max(margin, left) + window.scrollX + "px";
    menu.style.top = top + window.scrollY + "px";
  }

  function openMenu(toggle, component) {
    menu.innerHTML = "";
    menu.appendChild(menuHeading());
    component.formats.forEach(function (format) { menu.appendChild(menuRow(component, format)); });
    menu.hidden = false;
    placeMenu(toggle);
    toggle.setAttribute("aria-expanded", "true");
    openToggle = toggle;
    menu.querySelector("button").focus();
  }

  function moveFocus(delta) {
    var buttons = Array.prototype.slice.call(menu.querySelectorAll("button"));
    var next = buttons.indexOf(document.activeElement) + delta;
    buttons[(next + buttons.length) % buttons.length].focus();
  }

  menu.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown") { event.preventDefault(); moveFocus(1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); moveFocus(-1); }
    else if (event.key === "Escape") { event.stopPropagation(); closeMenu(); }
  });
  document.addEventListener("pointerdown", function (event) {
    if (!menu.hidden && !menu.contains(event.target) && event.target.closest(".tool-toggle") !== openToggle) {
      closeMenu();
    }
  });
  window.addEventListener("resize", closeMenu);

  /* ---------------------------------------------------------------- setup */

  var pageName = slug(window.location.pathname.split("/").filter(Boolean).pop() || "home");
  var counts = {};

  function nameOf(label, title) {
    if (label) return pageName + "-" + slug(label.textContent);
    counts[title] = (counts[title] || 0) + 1;
    return pageName + "-" + title + "-" + counts[title];
  }

  /* A scrolling element would carry an absolutely placed button along with its content,
     so such a component sits in a holder of its own. */
  function wrapInHost(element) {
    var host = document.createElement("div");
    element.parentNode.insertBefore(host, element);
    host.appendChild(element);
    return host;
  }

  function makeToggle(component, title) {
    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "tool-toggle iconbtn";
    toggle.innerHTML = icons.save;
    toggle.title = "Export";
    toggle.setAttribute("aria-label", "Export " + title);
    toggle.setAttribute("aria-haspopup", "menu");
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", function () {
      var isOpen = openToggle === toggle;
      closeMenu();
      if (!isOpen) openMenu(toggle, component);
    });
    return toggle;
  }

  /* One click copies the code, with no menu in the way. */
  function makeCopyToggle(element) {
    var label = "Copy source";
    var button = document.createElement("button");
    button.type = "button";
    button.className = "tool-toggle iconbtn";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = '<span class="export-icon">' + icons.copy + "</span>";
    button.addEventListener("click", function () {
      copyText(element.querySelector("code").textContent.replace(/\n$/, "")).then(function () {
        flash(button, icons.done, "Copied");
      }).catch(function (error) {
        console.error(error);
        flash(button, icons.failed, "Could not copy");
      });
    });
    return button;
  }

  /* A code block or equation has no caption, so its buttons float at a corner. `side` is
     the corner's side, `element` the component whose margins the host contains, and
     `inset` their distance from that component's edges. */
  function makeCorner(component, side, element, inset) {
    component.host.classList.add("tool-host");
    var tools = document.createElement("div");
    var style = getComputedStyle(element);
    var margin = side === "left" ? style.marginLeft : style.marginRight;
    tools.className = "tool-group tool-" + side;
    tools.style.top = "calc(" + style.marginTop + " + " + inset + ")";
    tools.style[side] = "calc(" + margin + " + " + inset + ")";
    component.host.appendChild(tools);
    return tools;
  }

  function addFigureToggles() {
    document.querySelectorAll(".prose figure").forEach(function (figure) {
      var isTable = figure.matches(".table");
      var target = figure.querySelector(isTable ? "table" : "svg, img");
      var tools = figure.querySelector(".tool-group");
      if (!target || !tools) return;
      var title = isTable ? "table" : "figure";
      tools.appendChild(makeToggle({
        host: figure,
        target: target,
        kind: isTable ? "table" : "figure",
        name: nameOf(figure.querySelector(".caplabel"), title),
        formats: isTable ? tableFormats() : target.matches("svg") ? svgFormats() : imageFormats
      }, title));
    });
  }

  function addCodeToggles() {
    document.querySelectorAll(".prose div.highlight").forEach(function (element) {
      var component = {
        host: wrapInHost(element),
        target: element,
        kind: "code",
        name: nameOf(null, "code"),
        formats: imageFormats
      };
      var tools = makeCorner(component, "right", element, "0.4rem");
      tools.appendChild(makeCopyToggle(element));
      tools.appendChild(makeToggle(component, "code"));
      element.addEventListener("click", function () { component.host.classList.toggle("tool-tapped"); });
    });
  }

  /* An equation's number sits at the right, and its left edge is free. */
  function addEquationToggles() {
    document.querySelectorAll(".prose div.arithmatex").forEach(function (element) {
      var component = {
        host: wrapInHost(element),
        target: element,
        kind: "equation",
        name: nameOf(null, "equation"),
        formats: equationFormats()
      };
      makeCorner(component, "left", element, "0.25rem").appendChild(makeToggle(component, "equation"));
    });
  }

  addFigureToggles();
  addCodeToggles();
  addEquationToggles();
})();
