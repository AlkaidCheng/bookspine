---
title: Basics
summary: Every numbered element on one page.
references:
  first-paper: A. Author, *A title*, Journal **1** (2020) 1, <https://example.org/journal/2020/first_paper.html>.
---

Text with a citation [@first-paper] and a link to
[the split chapter](split/index.md).

## Measures

$$
x = 1 \label{eq:one} \glossary{Unit value}
$$

![A flow of steps](figures/flow.svg)

| Name | Value |
|------|-------|
| a    | 1     |

Table: A captioned table.

| Name | Value |
|------|-------|
| b    | 2     |

### Detail

!!! definition "Term"
    \glossary
    A definition.

!!! note
    A side fact.

## Further reading

Nothing further.

## Examples

![A raster figure](figures/gradient.png)

| Symbol | Meaning    | Source                                |
|:-------|:----------:|--------------------------------------:|
| $x_1$  | **first**  | [a page](https://example.org/a_page)  |
| `a|b`  | *second*   | 50% of $\vec{p}$ & more               |

Table: Marks of every kind.

```python
def add(a, b):
    return a + b
```

A title, marked lines and line numbers:

```python title="add.py" hl_lines="2"
def add(a, b):
    return a + b
```

```python linenums="10"
def add(a, b):
    return a + b
```

## Marks

A footnote[^short], the same one again[^short], and a longer one[^long]. Press
++ctrl+alt+delete++ to restart the HTML page, or run `#!python add(1, 2)` with
\(a = 1\).

A paragraph with an id.
{: #marked-paragraph .marked }

\[
y = 2
\]

[^short]: A short note.
[^long]: A longer note.

    With a second paragraph.

*[HTML]: HyperText Markup Language
