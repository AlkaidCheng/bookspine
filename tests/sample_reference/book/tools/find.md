---
title: Finding files
summary: "Count files with `find`."
---

Search a tree with `find <dir> -name x`, then [read plain text](plain.md).

## Count files

=== "Syntax"

    ```text
    find <dir> | wc -l
    ```

=== "Example"

    ```bash
    find . | wc -l
    ```

![A flow](figures/flow.svg)

## Count by type

Use `-type f`.
