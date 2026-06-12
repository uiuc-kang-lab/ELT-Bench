# SQL Error Classification - Annotation Package

## 📦 What's in This Package

This package contains everything you need to participate in the SQL error classification study:

### 📄 Instruction Files
- **MESSAGE_TO_ANNOTATORS.txt** - Overview and getting started guide
- **README_ANNOTATION.md** - Study purpose and file structure
- **annotation_protocol.md** - Complete taxonomy with definitions and examples (READ THIS!)
- **quick_reference.md** - Quick reference cheat sheet (keep open while working)
- **sampled_files.txt** - List of 50 files to annotate

### 📝 Template
- **annotation_template.txt** - Copy this and fill in your classifications

### 📂 Database Directories (81 folders)
All the debug files you'll need to read are organized by database name (e.g., `sales/`, `books/`, `apple_store/`, etc.)

---

## 🚀 Quick Start

1. **Read in this order:**
   - MESSAGE_TO_ANNOTATORS.txt (5 min)
   - annotation_protocol.md (20 min)
   - Keep quick_reference.md open as reference

2. **Copy the template:**
   ```bash
   cp annotation_template.txt annotations_yourname.txt
   ```

3. **Start annotating:**
   - Open sampled_files.txt to see the 50 files
   - Read each debug file
   - Assign ONE category per column
   - Save frequently!

4. **Submit when done:**
   - Send your completed `annotations_yourname.txt` file
   - Optionally include notes on difficult cases

---

## ⚠️ Important Rules

❌ **DO NOT:**
- Look for or use any existing annotation files
- Discuss classifications with other annotators before completing
- Search for prior analysis results

✅ **DO:**
- Work independently based solely on the taxonomy
- Focus on identifying the ROOT CAUSE of each error
- Make your best judgment on ambiguous cases
- Take notes on particularly difficult cases (optional)

---

## 📊 What You're Annotating

Each debug file documents a single column's SQL generation error. You'll classify it into one of these categories:

**AGENT ERRORS** (fixable through better SQL):
- Category 1: Ambiguous Data Model Description
- Category 2: Logic Error (Flawed SQL)
- Category 3: INNER vs LEFT JOIN Issues
- Category 4.1: Missing Join
- Category 4.2: Wrong Table or Column
- Category 6: Domain Knowledge
- Category 7: NULL Handling Issues
- Category 8: Key Generation Issues

**BENCHMARK ERRORS** (require benchmark fixes):
- Category 5.1: Actual Match (False Positive)
- Category 5.2: Format Mismatch (False Positive)
- Category 5.3: Duplicated Rows in GT (False Positive)
- Category 5.4: NULL Mismatch (False Positive)
- Category 5.5: Row Ordering (False Positive)
- Category 5.6: Other False Positive
- Category 9: Unknown Calculation Errors

---

## 💡 Tips

- **Time estimate:** 2-3 hours (can be split across sessions)
- **Per file:** About 2-4 minutes average
- **When stuck:** Make your best judgment and note it
- **Consistency:** Try to classify similar cases the same way

---

## 📧 Questions?

If you have questions about:
- **The process or taxonomy:** Contact the study coordinator
- **Specific classifications:** Document your reasoning and make your best judgment

Remember: We can't discuss specific classifications until after all annotators complete their work (to maintain independence).

---

## 🎯 Your Goal

Independently classify 50 SQL error cases to help validate the reliability of our error taxonomy through inter-annotator agreement analysis.

**Your independent judgment is crucial for this research. Thank you for participating!**

---

**Package Version:** 2026-03-24
**Contains:** 50 sampled cases from ELT-Bench SQL error analysis
