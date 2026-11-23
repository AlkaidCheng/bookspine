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

A mark shows where an equation written for the full width may break on a narrow screen,

$$
\begin{aligned}
& (a + b)^5 = a^5 + 5 a^4 b + 10 a^3 b^2
\narrowbreak + 10 a^2 b^3 + 5 a b^4 + b^5 ,
\end{aligned}
\label{eq:fifth-power}
$$

another parts two formulas,

$$
\begin{aligned}
& \cos^2 x + \sin^2 x = 1 ,
\narrowsep \cosh^2 x - \sinh^2 x = 1 ,
\end{aligned}
$$

and an equation without marks is drawn smaller where it is wider than the text:

$$
e^x = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \frac{x^4}{4!} + \dots
$$

![A flow of steps from $x_0$ to \(x_1\) [@first-paper].](figures/flow.svg)

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

```python title="add.py" linenums="9"
# A comment long enough to run past the edge of the block, which scrolls instead of wrapping, as every block with line numbers does.
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

??? tip "A collapsible box"

    Closed until a reader opens it.

## Tabs

=== "Syntax"

    ```text
    copy <source> <target>
    ```

=== "Example"

    ```bash
    copy notes.txt backup/notes.txt
    ```

Tabs of code alone make a card, and tabs holding cards switch between them.

=== "Linux"

    === "Syntax"

        ```text
        stat -c %s <file>
        ```

    === "Example"

        ```bash
        stat -c %s notes.txt
        ```

=== "macOS"

    === "Syntax"

        ```text
        stat -f %z <file>
        ```

    === "Example"

        ```bash
        stat -f %z notes.txt
        ```

Any other tabs keep a plain bar.

=== "Python"

    Read the file with `pathlib`:

    ```python
    Path("notes.txt").read_text()
    ```

=== "Shell"

    Read the file with `cat`.
