# Error Classification Annotation Study

## Purpose

This study measures **inter-annotator agreement** on classifying SQL generation errors. Multiple annotators will independently classify the same 50 debug files, then we'll compare results to:

1. Assess reliability of the error taxonomy
2. Identify ambiguous categories that need refinement
3. Measure consistency in Agent vs Benchmark attribution
4. Compare annotations across all annotators

## For Annotators

### What You Need

1. **Annotation Protocol:** `annotation_protocol.md` - READ THIS FIRST
   - Complete error taxonomy with definitions and examples
   - Clear decision rules and prioritization guidelines
   - Common pitfalls to avoid

2. **Quick Reference:** `quick_reference.md` - Keep open while working
   - One-page decision tree and examples
   - Printable cheat sheet

3. **Files to Annotate:** 50 debug files in this directory
   - Each file documents one column's error
   - Location: subdirectories like `./sales/`, `./books/`, etc.
   - Full list in `sampled_files.txt`

4. **Output Template:** `annotation_template.txt`
   - Copy this file and fill in your categories
   - Save as `annotations_<yourname>.txt`

**Note:** Do NOT read `experiment_report.md` or `categorization_chris.md` before completing your annotations, as these contain results from other annotators that could bias your classifications.

### Quick Start

```bash
# 1. Read the protocol
cat annotation_protocol.md

# 2. Copy the template
cp annotation_template.txt annotations_yourname.txt

# 3. Start annotating
# Read each debug file and assign a category
# Example: ./sales/summary__sales__sales__customers_ABOVE_AVERAGE_BOUGHT_QUANTITY.md

# 4. Submit your completed file
```

### Time Commitment

- **Expected time:** 2-3 hours for 50 columns
- **Average per column:** 2-4 minutes
- Can be done in multiple sessions

## File Structure

```
method_debug_summaries/
├── README_ANNOTATION.md          ← You are here
├── annotation_protocol.md         ← Detailed instructions and taxonomy
├── quick_reference.md            ← Quick reference cheat sheet
├── annotation_template.txt        ← Copy this and fill it in
├── sampled_files.txt             ← List of 50 files to annotate
│
├── _analysis_results/            ← ⚠️ DO NOT LOOK - Contains prior results
│
├── sales/
│   └── summary__sales__...md     ← Debug files to read
├── books/
│   └── summary__books__...md
└── [79 other database folders]/
    └── ...
```

**Note:** The `_analysis_results/` directory contains preliminary results and should NOT be accessed until after you complete your independent annotations.

## Error Categories

See `annotation_protocol.md` for complete definitions and examples of all categories.

## Analysis Plan

After collecting annotations from multiple annotators, we will:

1. **Calculate inter-annotator agreement**
   - Cohen's Kappa between annotator pairs
   - Krippendorff's Alpha across all annotators
   - Agreement on high-level Agent vs Benchmark split

2. **Compare across all annotators**
   - Agreement rates between all annotator pairs
   - Identify systematic differences
   - Analyze difficult/ambiguous cases

3. **Validate taxonomy**
   - Find categories with high disagreement
   - Refine definitions if needed
   - Document edge cases

4. **Report findings**
   - Overall agreement metrics
   - Category-level reliability
   - Recommendations for taxonomy improvements

## Questions?

If you have questions while annotating:
- Document unclear cases
- Make your best judgment
- Note reasoning for difficult decisions
- We'll discuss in debrief

## Contact

[Add contact information here]

## Timeline

- Annotation deadline: [TBD]
- Analysis completion: [TBD]
- Results sharing: [TBD]
