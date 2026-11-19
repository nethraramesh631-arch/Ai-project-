"""Local interactive dashboard for reviewing event registrations."""
import csv
import html
import io
import os
from collections import Counter

os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

import streamlit as st

from main import BASE_DIR, FIELDS, extract_locally, process, read_csv


st.set_page_config(page_title="Registration Desk", layout="wide")
st.markdown(
    """
    <style>
    :root { --ink: #172b27; --green: #164b3c; --mint: #d7eee3; --lime: #c4e86b;
            --paper: #f7f8f3; --line: #dce3da; --muted: #65756e; --amber: #e8ad4c; }
    .stApp { background: var(--paper); color: var(--ink); font-family: 'Segoe UI', sans-serif; }
    [data-testid="stSidebar"] { background: #edf1e9; border-right: 1px solid var(--line); }
    .block-container { max-width: 1440px; padding-top: 2rem; padding-bottom: 3rem; }
    h1, h2, h3 { color: var(--ink); }
    h1 { font-family: Georgia, serif; font-weight: 500; }
    [data-testid="stMetric"] { background: white; border: 1px solid var(--line);
      border-radius: 6px; padding: 16px 18px; }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--green); }
    .masthead { display:flex; align-items:center; justify-content:space-between;
      gap:20px; background:var(--green); color:white; padding:24px 28px;
      border-radius:6px; margin-bottom:22px; }
    .masthead h1 { color:white; font-size:32px; margin:0; }
    .masthead p { margin:5px 0 0; color:#d5e7db; font-size:14px; }
    .local-mark { color:var(--lime); font:500 11px Consolas, monospace;
      letter-spacing:0.06em; white-space:nowrap; }
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
      border:1px solid var(--line); border-radius:6px; overflow:hidden; }
    div.stButton > button, div.stDownloadButton > button {
      border-radius:4px; border-color:var(--green); color:var(--green); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("### REGISTRATION DESK")
uploaded_file = st.sidebar.file_uploader("Registration CSV", type=["csv"])

try:
    if uploaded_file:
        text = uploaded_file.getvalue().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not {"id", "entry"}.issubset(reader.fieldnames or []):
            st.error("CSV must contain columns named id and entry.")
            st.stop()
        records = list(reader)
        source_name = uploaded_file.name
    else:
        records = read_csv(BASE_DIR / "registrations.csv")
        source_name = "registrations.csv"
except (UnicodeDecodeError, csv.Error, OSError, ValueError) as error:
    st.error(f"Could not read this CSV: {error}")
    st.stop()

records = [
    {"id": str(record.get("id") or "").strip(),
     "entry": str(record.get("entry") or "").strip()}
    for record in records
]
if not records:
    st.info("This CSV has no registration rows.")
    st.stop()

st.markdown(
    f"<div class='masthead'><div><h1>Registration Desk</h1>"
    f"<p>{html.escape(source_name)} &nbsp; / &nbsp; {len(records)} registrations</p></div>"
    "<span class='local-mark'>LOCAL MODE &nbsp; / &nbsp; NO API</span></div>",
    unsafe_allow_html=True,
)

initial_rows = [
    {"id": record["id"], "entry": record["entry"],
     **extract_locally(record["entry"])}
    for record in records
]
with st.expander("Review extracted fields", expanded=True):
    reviewed_rows = st.data_editor(
        initial_rows,
        key="reviewed_registrations",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["id", "entry"],
        column_config={
            "id": st.column_config.TextColumn("ID", width="small"),
            "entry": st.column_config.TextColumn("Original entry", width="large"),
            "name": st.column_config.TextColumn("Name"),
            "phone": st.column_config.TextColumn("Phone"),
            "email": st.column_config.TextColumn("Email"),
            "year": st.column_config.TextColumn("Year"),
            "branch": st.column_config.TextColumn("Branch"),
        },
    )

extractions = iter([
    {field: row.get(field) for field in FIELDS}
    for row in reviewed_rows
])
clean_rows, problem_rows = process(records, lambda _entry: next(extractions))
valid_count = len(clean_rows)
needs_fix_count = sum(row["status"] == "needs_fix" for row in problem_rows)
duplicate_count = sum(row["status"] == "duplicate" for row in problem_rows)

metric_columns = st.columns(4)
metric_columns[0].metric("Registrations", len(records))
metric_columns[1].metric("Valid", valid_count)
metric_columns[2].metric("Needs review", needs_fix_count)
metric_columns[3].metric("Duplicates", duplicate_count)

st.subheader("Registration status")
st.bar_chart(
    {"Status": ["Valid", "Needs review", "Duplicates"],
     "Count": [valid_count, needs_fix_count, duplicate_count]},
    x="Status",
    y="Count",
    height=230,
)

valid_by_id = {row["id"]: row for row in clean_rows}
problems_by_id = {row["id"]: row for row in problem_rows}
results = []
for record in records:
    if record["id"] in problems_by_id:
        results.append(problems_by_id[record["id"]])
    else:
        results.append({
            **valid_by_id[record["id"]],
            "status": "valid",
            "duplicate_of": None,
            "reasons": "",
            "original_entry": record["entry"],
        })

st.subheader("Review queue")
filter_column, search_column = st.columns([1, 2])
selected_status = filter_column.selectbox(
    "Status", ["All", "valid", "needs_fix", "duplicate"]
)
search_text = search_column.text_input("Search registrations", placeholder="Name, ID, email or reason")
visible_rows = [
    row for row in results
    if (selected_status == "All" or row["status"] == selected_status)
    and (not search_text or search_text.casefold() in " ".join(
        str(value or "") for value in row.values()
    ).casefold())
]
st.dataframe(visible_rows, hide_index=True, use_container_width=True)
st.caption(f"Showing {len(visible_rows)} of {len(results)} registrations")

def csv_download(rows, fieldnames):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


summary_lines = [
    "EVENT REGISTRATION CLEANER - SUMMARY",
    f"Total entries: {len(records)}",
    f"Valid: {valid_count}",
    f"Needs fixing: {needs_fix_count}",
    f"Duplicates: {duplicate_count}",
    "",
    "Human checkpoint: Review every non-valid record before changing contact details.",
]
downloads = st.columns(3)
downloads[0].download_button(
    "Download clean list",
    csv_download(clean_rows, ["id", "name", "phone", "email", "year", "branch"]),
    "clean_list.csv",
    "text/csv",
)
downloads[1].download_button(
    "Download review list",
    csv_download(problem_rows, [
        "id", "name", "phone", "email", "year", "branch", "status",
        "duplicate_of", "reasons", "original_entry",
    ]),
    "problems.csv",
    "text/csv",
)
downloads[2].download_button(
    "Download summary",
    "\n".join(summary_lines),
    "summary.txt",
    "text/plain",
)