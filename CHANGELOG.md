# Changelog

## 0.1.0

- Add the `guidebook build` command, which turns a project's `book.yaml` and `book/` into a static site (#1).
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
- Speed up `guidebook build` by skipping inline patterns that cannot match a text (#11).
