# Changelog

## 0.1.0

- Add the `bookspine build` command, which turns a project's `book.yaml` and `book/` into a static site (#1).
- Add export menus to tables, figures, code blocks and equations, controlled by the `export_menus` key (#2).
- Open figures and tables enlarged from a button instead of a click on them, as `enlarge_tables` now describes (#3).
- Add the `\glossary` tag, which indexes terms and equations on glossary pages, controlled by the `glossary` key (#4).
- Add the `help_page` key, which names a page of conventions and resources linked from the foot of the sidebar (#5).
- Keep the `.topbar` search and colour scheme buttons at the right edge of the page (#6).
- Wrap links that show their own address between its elements, with no added hyphen, so a long URL no longer widens the page (#7).
- Wrap long lines of code with a hanging indent instead of scrolling them sideways, controlled by the `wrap_code` key (#8).
- Stop outlining code in red where the highlighter cannot parse it (#8).
- Show code as written, without the code font's ligatures, on the page and in PNG exports (#9).
- Keep the arrow of an `.external` link on the line that holds the end of the link (#9).
- Load MathJax only on pages where it has something to do (#10).
- Convert pages with pyromark, which follows CommonMark and halves build times, and require Python 3.11 (#12).
- Add abbreviations, keys, paragraph attributes, `\(…\)` math and code block options to `convert_markdown`, and keep the footnotes the theme styles (#13).
- Style code blocks with `linenums` in the theme's colours, and stop `pygments_dark` colouring their numbers in the light scheme (#14).
- Move the `.tool-group` of a code block with its margins when the window resizes (#14).
- Keep coloured inline code clear of the text before it at phone width (#14).
- Show a heading's `&` as written in the sidebar, where `number_headings` passed on its HTML entity (#15).
- Expand tabs in `convert_markdown`, so the text of a box or footnote can be indented with them (#15).
- Carry the licences of the code copied from pymdown-extensions and Python-Markdown in `LICENSES/` (#15).
- Convert pages with pulldown-cmark directly, through the compiled `bookspine._markdown` module, in place of pyromark (#16).
