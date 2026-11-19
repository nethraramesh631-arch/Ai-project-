Event Registration Cleaner
A console Python tool that extracts event registration fields using an LLM, validates extracted facts against the original text, cleans only with deterministic Python rules, detects duplicates, and writes CSV/text reports.

Setup
Install Python 3.10 or later.
Put registrations.csv beside main.py. It needs id and entry columns.
Set the API key in your terminal; never place it in source files:
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-4o-mini"
Run:
python main.py
Without a key, the program safely marks each row as an LLM extraction failure instead of guessing.

Outputs
clean_list.csv: valid registrations only
problems.csv: invalid and duplicate registrations with reasons
summary.txt: status counts and valid counts by branch/year
Dashboard
Install dependencies and launch the Streamlit dashboard:

python -m pip install -r requirements.txt
python -m streamlit run app.py
Open http://localhost:8501. Set OPENAI_API_KEY in the terminal before launching. The dashboard never requests or stores the key.

Tests
python -m unittest test_main.py
python eval_harness.py
Project Documents
SPECIFICATION.md
system_prompt.txt
JUDGMENT_FRAMEWORK.md
COST_LATENCY.md
RED_TEAM_RESULTS.md
AI_DECISION_JOURNAL.md
REFLECTION.md
The event team is the human checkpoint. They contact every person listed in problems.csv.# Ai-project-