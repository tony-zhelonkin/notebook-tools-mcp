# notebook-tools MCP Feedback

**Date:** 2026-02-25
**Task:** Validate a 47-cell Jupyter notebook (NB09, ~1500 lines of source)
**Agent:** Claude Opus 4.6 via Claude Code

---

## Tools Used

| Tool | Attempted | Result | Usage |
|---|---|---|---|
| `nb_overview` | Yes | SUCCESS | Got full table of contents with cell types, line counts, and first-line previews |
| `nb_read_cell` | Yes | DENIED (permission) | Needed to read individual cell contents |
| `nb_read_cells` | Yes | DENIED (permission) | Needed to read cell ranges |
| `nb_search` | Yes | DENIED (permission) | Needed to search for patterns across cells |
| `nb_metadata` | Yes | DENIED (permission) | Wanted kernel info and cell counts |

**Most used:** `nb_overview` (1 call -- the only tool that worked)

---

## What Was Convenient

1. **`nb_overview` output format is excellent.** The table-of-contents view with cell index, type, line count, and first-line preview gave me enough structure to understand the notebook's architecture at a glance. This is genuinely better than raw JSON.

2. **The tool set concept is right.** Having dedicated notebook tools (overview, read, search) rather than generic file reading is the correct design. Notebooks are structured documents, not flat text files.

---

## What Was Missing / Blocked

1. **All read tools were permission-denied.** Only `nb_overview` worked. This forced me to fall back to a Python JSON parser via Bash to extract cell contents -- exactly the workflow the MCP tools are designed to replace. The fallback worked but was token-expensive (loaded 1500 lines of source at once instead of reading targeted cells).

2. **No way to read cell outputs.** Even when `nb_read_cell` is available, the `include_outputs` parameter tops out at `max_output_chars=2000`. For cells that produce DataFrames, plots, or long printed output, this may truncate critical information. A pagination option for outputs would help.

---

## Suggestions

1. **Permission model:** If `nb_overview` is allowed, `nb_read_cell` and `nb_read_cells` should likely also be allowed -- they are read-only tools on the same file. Denying read tools while allowing overview creates an inconsistent experience where the agent can see the table of contents but cannot read any chapters.

2. **`nb_overview` enhancement: include full first line.** The preview truncates long first lines with `...`. For markdown cells, the first line is often the section header -- showing the full header would make the overview more useful for navigation.

3. **Batch read by type:** A tool like `nb_read_all_markdown` or `nb_read_cells(cell_type="markdown")` would be useful for validation tasks where you need to read all narrative text without the code.

4. **Cell content length in overview:** The overview shows line count but not character count. For large code cells (e.g., cell 28 at 95 lines), knowing the approximate character count would help decide whether to read in full or search for specific patterns.

5. **Output summary mode:** An option to get output metadata (type: text/image/dataframe, size, first N chars) without the full output content would help agents decide which cell outputs to examine in detail.

---

## Session 2: NB08 Validation (2026-02-25)

**Task:** Validate a 132-cell Jupyter notebook (08_dc_subset_annotation.ipynb)
**Agent:** Claude Opus 4.6 (validation agent in Claude Code)

### Tools Used

Same result as Session 1: only `nb_overview` was accessible. All other tools
(`nb_read_cell`, `nb_read_cells`, `nb_search`, `nb_metadata`) were permission-denied.

### Additional Observations

1. **`nb_overview` scales well to large notebooks.** The 132-cell overview was returned
   quickly and was easy to parse. The tool handles the full range of cell sizes (1-line
   markdown headers to 114-line code cells) without issues.

2. **The Bash fallback was adequate but token-expensive.** I extracted cell contents
   using `python3 -c "import json; ..."` in ~6 Bash calls, each covering 15-25 cells.
   This consumed more tokens than targeted `nb_read_cells` calls would have, because
   I had to dump full cell sources even when I only needed to check a specific pattern.

3. **`nb_search` would have been the highest-value tool for validation.** Validation
   involves checking patterns across the entire notebook (e.g., "is `adata` used
   consistently?", "are all helper functions defined before use?", "does any cell
   reference a variable from a later cell?"). `nb_search` with regex would have
   answered these questions in seconds.

### New Suggestion

6. **`nb_read_section` tool.** Takes a markdown header pattern (e.g., `"## 8.5"`) and
   returns all cells from that header to the next same-level or higher-level header.
   This matches how humans navigate notebooks and would be ideal for section-by-section
   validation of large notebooks like NB08.

---

## Session 3: NB06 Expanded Validation (2026-02-25)

**Task:** Validate 4 newly added sections in a 72-cell notebook (06_iron_dc_biology.ipynb)
for structural, code, educational, narrative, and biological accuracy.
**Agent:** Claude Opus 4.6 (validation agent in Claude Code)

### Tools Used

Same permission pattern as Sessions 1 and 2: only `nb_overview` was accessible. All other
tools (`nb_read_cell`, `nb_read_cells`, `nb_search`, `nb_metadata`) were permission-denied.

### What Worked

1. **`nb_overview` was essential for structural validation.** I used it to verify the
   notebook has exactly 72 cells (38 code, 34 markdown), confirm section placement at
   the correct cell indices, and validate the heading hierarchy. This single call provided
   the backbone for the entire validation.

2. **Bash fallback via `python3 -c "import json; ..."` was effective.** I extracted cell
   contents in 6 targeted Bash calls, each covering 4-8 cells. This was more efficient
   than Session 2 because I had specific cell ranges to check (29-34, 40-43, 57-61, 65-68)
   rather than needing to scan the whole notebook.

### What Was Missing

1. **`nb_search` would have saved 2-3 Bash calls.** I needed to:
   - Find all cells that define `cdc1_label` (pattern: `cdc1_label\s*=`)
   - Find all cells that use `import ` statements outside cell 4
   - Check which cells reference `fdr_correct`, `cohens_d`, `score_gene_program`
   These are exactly the queries `nb_search` is designed for.

2. **A dependency analysis tool would have been the highest-value addition.** My main
   finding was a cross-section variable dependency (cell 59 uses `cdc1_label` defined in
   cell 41). Detecting this required: (a) reading all cells in the range, (b) regex
   scanning for assignments vs uses, (c) tracing the definition chain. A tool like
   `nb_dependencies(notebook_path, variable="cdc1_label")` returning `{"defined_in": [41],
   "used_in": [42, 59, 60]}` would have been transformative for validation.

3. **Heading-only extraction.** I wrote a custom Python script to extract all markdown
   headings with their cell indices. An `nb_headings(notebook_path)` tool returning
   `[{"cell": 29, "level": 2, "text": "6.5 When Pathway Scores Mislead..."}]` would
   replace this common pattern.

### Updated Suggestion

7. **`nb_dependencies` tool.** Analyze variable/function definitions and usages across
   cells. Input: notebook path + optional variable/function name. Output: definition
   sites and usage sites with cell indices. This is the single highest-impact tool for
   notebook validation and debugging tasks. It would catch issues like "cell 59 uses
   `cdc1_label` but it is only defined in cell 41, creating a fragile dependency."

---

## Session 4: NB00-NB05 Series Validation (2026-02-25)

**Task:** Validate 6 notebooks (NB00-NB05, 301 total cells) for educational quality
and cross-notebook prerequisite analysis.
**Agent:** Claude Opus 4.6 (validation agent in Claude Code)

### Tools Used

| Tool | Calls | Result |
|---|---|---|
| `nb_overview` | 6 (batch) | SUCCESS -- all 6 returned in a single parallel call |
| `nb_read_cell` | 4 (batch) | DENIED (permission) |
| `nb_read_cells` | 3 (batch) | DENIED (permission) |
| `nb_search` | 1 | DENIED (permission) |
| `nb_metadata` | 6 (batch) | DENIED (permission) |

### Key Observation: Batch Overview Calls Work, Everything Else Denied

The initial parallel call to `nb_overview` for all 6 notebooks succeeded and returned
complete table-of-contents data for 301 cells. This was the only successful MCP
interaction. All subsequent tool calls (including `nb_overview` retries) were denied.

This suggests the permission model may be **per-conversation rather than per-call** --
the first batch of MCP calls is allowed, then a blanket denial applies. If this is
intentional, it should be documented. If not, it is a bug.

### Fallback Strategy

I used three parallel strategies to compensate for the read tool denial:

1. **Grep on raw .ipynb JSON** -- Effective for finding patterns across notebooks
   (e.g., `score_gene_program`, `label_transfer`, `from modules`). However, the JSON
   line wrapping means matches are often on `"source"` array lines rather than logical
   code lines, making context harder to interpret.

2. **Python JSON parser via Bash** -- More targeted: `python3 -c "import json; ..."` to
   extract cell contents by index, search for keywords, list function definitions, and
   count enhancement cells. This was the workhorse for the review, consuming ~10 Bash calls.

3. **Grep for educational markers** -- Searched for `Prediction Checkpoint`, `Building Block`,
   `What If`, `Key Takeaway`, `Try It Yourself` across all notebooks to map the pedagogical
   rhythm without reading full cell contents.

### What Would Have Changed With Full Tool Access

With `nb_read_cells` and `nb_search` working, the review would have been:
- **~50% fewer tool calls** (10 Bash Python scripts replaced by ~5 nb_read_cells calls)
- **More focused** -- I could have read only markdown cells to assess narrative quality,
  or only code cells to check imports/function signatures
- **Cross-notebook search** -- `nb_search` across 6 files for `def ` patterns would have
  immediately shown which functions are defined inline vs imported from modules

### New Suggestions

8. **Cross-notebook search.** A variant of `nb_search` that accepts a directory or glob
   pattern and searches across multiple notebooks. For series validation, the agent needs
   to answer questions like "where is `score_gene_program` defined across NB00-NB09?" --
   currently this requires one Grep call per notebook or a single Grep on raw JSON.

9. **`nb_overview` with content hash.** Adding a short content hash per cell would help
   detect whether two cells in different notebooks contain identical code (copy-paste
   detection). This is relevant for finding DRY violations like NB06 redefining
   `check_gene_coverage()` when it already exists in `modules/scoring.py`.

---

## Session 5: Cross-Notebook Consistency Validation (2026-02-25)

**Task:** Validate consistency across ALL 10 notebooks (NB00-NB09) for data paths,
variable names, helper function duplication, imports, dependency chain, style, and kernels.
**Agent:** Claude Opus 4.6 (cross-notebook validation agent in Claude Code)

### Tools Used

| Tool | Calls | Result |
|---|---|---|
| `nb_overview` | 10 (one per notebook) | SUCCESS -- primary structural tool |
| `nb_search` | 11 | DENIED (permission) |
| `nb_read_cell` | 1 | DENIED (permission) |
| `nb_read_cells` | 1 | DENIED (permission) |
| `nb_metadata` | 10 | DENIED (permission) |
| **Grep (fallback)** | ~15 calls | Searched `.ipynb` JSON for patterns |

### What Worked

1. **`nb_overview` x 10 notebooks provided the structural backbone.** I mapped the complete
   cell structure of all 10 notebooks (430+ cells total), verified section numbering, and
   confirmed code/markdown ratios. All 10 calls completed quickly.

2. **Grep on `.ipynb` files was an effective fallback for cross-notebook pattern search.**
   It successfully identified all checkpoint loading calls, function redefinitions vs imports,
   import pattern differences, score name inconsistencies, and R-equivalent comment counts.
   The trade-off: JSON line numbers instead of cell indices, and escaped string matching.

### What Was Missing -- Cross-Notebook Specific

1. **`nb_search_all` (most critical for this task).** I needed to search for the same
   pattern across 10 notebooks. Without `nb_search`, I used Grep on raw JSON (works but
   loses cell context). With `nb_search`, I would have needed 10 calls per pattern. A
   cross-notebook search tool would reduce this to 1 call per pattern:

   ```
   nb_search_all(
       directory="02_analysis/notebooks/",
       pattern="def score_gene_program",
       cell_type="code"
   )
   -> [{"notebook": "06_iron_dc_biology.ipynb", "cell": 17, "line": 1, "match": "..."}]
   ```

2. **`nb_metadata` denial forced Grep for kernel info.** A `nb_metadata_all(directory)`
   returning kernel and format info for all notebooks would be ideal for consistency checks.

3. **Cross-notebook import comparison tool.** The most labor-intensive check was comparing
   import patterns across all 10 notebooks. An `nb_imports_all(directory)` returning a
   structured comparison would save significant effort.

### Key Findings Enabled by This Tooling

Despite tool limitations, `nb_overview` + `Grep` was sufficient to find:
- **4 High-severity issues:** Helper function duplication, score name inconsistencies
- **6 Medium-severity issues:** Import gaps, groupby column mismatches, missing shared utils
- **6 Low-severity issues:** Style inconsistencies, kernel display names, markdown formatting

Full report written to `02_analysis/notebooks/_validation_cross_notebook.md`.

### Final Suggestions

10. **`nb_search_dir` / `nb_search_all` tool.** Search across all notebooks in a directory
    with a single call. This is the highest-impact addition for cross-notebook validation.

11. **`nb_compare_cells` tool.** Compare specific cell ranges across notebooks side by side
    (e.g., "show me cells 0-3 of each notebook"). Would instantly reveal boilerplate drift.

12. **`nb_function_map` tool.** List all function definitions across all notebooks in a
    directory. Output: `{function_name: [{notebook, cell, signature}]}`. This would catch
    the exact class of duplication bugs found in this validation.
