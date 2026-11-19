# Judgment Framework

| Part | What can go wrong? | What does the program decide? | Human checkpoint |
|---|---|---|---|
| Name extraction | Misspelled or incomplete name | Copies as written; title-cases only | Event team confirms unclear names |
| Phone extraction | LLM invents or changes digits | Fact-checks against original text; rejects unsupported number | Event team contacts registrant |
| Phone cleaning | Wrong prefix or digit count | Removes formatting and specified leading 91/0; validates 10 digits | Event team checks invalid numbers |
| Email extraction | LLM adds a missing domain ending | Exact text fact-check; no completion | Event team asks registrant to confirm |
| Email cleaning | Invalid email format | Lowercases and validates basic format only | Event team confirms invalid email |
| Year and branch | Ambiguous wording | Maps recognized year; unknown branch becomes other | Event team confirms missing/other value |
| Duplicate detection | Same person uses different formatting | Compares cleaned phone or email with earlier valid records | Event team checks duplicate identity |
| Reports | Incorrect extraction or false duplicate | Records reasons and original entry | Event team reviews all problems.csv rows |

## Named human checkpoint
The **event team contacts everyone listed in `problems.csv`** before changing any contact details or issuing certificates. No phone number or email is silently corrected.
