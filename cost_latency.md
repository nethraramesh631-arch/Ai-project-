# Cost and Latency Note

## API call count
The program sends one request per registration entry. Therefore, a file with 20 entries requires approximately 20 LLM API calls. A file with 100 entries requires approximately 100 calls. Python cleaning, validation, duplicate detection and report writing do not require LLM calls.

## Latency
Measure the actual time on the computer and network used for the demonstration. Sequential calls mean total runtime is approximately the sum of the individual request times plus local processing. For a classroom estimate only, if one request averages 1-3 seconds, 20 entries may take roughly 20-60 seconds. This is an estimate, not a service guarantee.

## Cost
Cost depends on the selected model, prompt length, output length, and current API token rates. Do not claim a fixed daily price without measuring token usage and checking current model pricing. A transparent estimate is:

`estimated cost = (input tokens / 1,000,000 × input price per million) + (output tokens / 1,000,000 × output price per million)`

For the final showcase, record the model, number of entries, total input/output tokens from API usage, and the applicable official price on the day of the run. The number of calls is approximately equal to the number of rows.
