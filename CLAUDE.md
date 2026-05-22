# PPR Streamlit — Project Guidelines

## Coding Behavior (Karpathy Guidelines)

### 1. Think Before Coding
- State assumptions explicitly before implementing. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so.
- If something is unclear, stop and name what's confusing.

### 2. Simplicity First
- Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No error handling for impossible scenarios.
- Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
- Touch only what must change. Don't improve adjacent code.
- Don't refactor things that aren't broken.
- Match existing style.
- Remove only imports/variables made unused by YOUR changes.
- Every changed line must trace directly to the user's request.

### 4. Goal-Driven Execution
- Transform tasks into verifiable goals before starting.
- For multi-step tasks, state a brief plan with a verify step for each.
- Strong success criteria: loop independently. Weak criteria: ask first.

## Project Context

- **Stack:** Python / Streamlit, pandas, reportlab, pypdf, anthropic SDK
- **Main file:** `app.py` — single-file Streamlit app
- **PDF generation:** `ppr_pdf_web.py` → `ppr_pdf.py`
- **Deployment:** Streamlit Cloud, branch `main`
- **API secrets:** `ANTHROPIC_API_KEY` in Streamlit Cloud secrets (`st.secrets`)
- **Session state:** project data lives in `st.session_state.dados` (aliased as `d`)
