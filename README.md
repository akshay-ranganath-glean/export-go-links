# Glean Go Links Export

`export_glean_golinks.py` is a read-only script that pulls the complete Go Links
(shortcuts) inventory from a Glean instance and writes it to CSV and JSON.

It calls Glean's paginated
[List Shortcuts API](https://developers.glean.com/api/client-api/shortcuts/listshortcuts)
(`POST /rest/api/v1/listshortcuts`) and never creates, updates, or deletes anything.

## Prerequisites

- Python 3.10 or newer
- A Glean API token authorized for an **admin** account (the API only returns
  shortcuts the authenticated user can see or edit, so a non-admin token yields a
  partial inventory)
- The base URL of your Glean instance, e.g. `https://your-company-be.glean.com`

## Setup

1. Install the dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

2. Create a `.env` file next to the script:

   ```dotenv
   GLEAN_BASE_URL=https://your-glean-instance
   GLEAN_API_TOKEN=your-authorized-bearer-token
   ```

   Variables already set in your shell take precedence over `.env`. Keep `.env`
   private and never commit it.

## Run

```bash
python3 export_glean_golinks.py
```

Example output:

```
Fetched page 1: 100 records
Fetched page 2: 100 records
Fetched page 3: 37 records
Exported 237 shortcuts.
API totalItemCount: 237
CSV:  /path/to/glean_golinks_export.csv
JSON: /path/to/glean_golinks_export.json
```

If the exported count does not match `totalItemCount`, the script prints a
warning. Do not treat the export as complete until that discrepancy is explained.

## How it works

```
.env / environment
        |
        v
  load_dotenv()  ->  GLEAN_BASE_URL, GLEAN_API_TOKEN
        |
        v
  fetch_all_shortcuts()
        |
        |   loop: POST /rest/api/v1/listshortcuts  {pageSize: 100, cursor?}
        |         <- {shortcuts: [...], meta: {hasNextPage, cursor, totalItemCount}}
        |   stop when meta.hasNextPage is false
        v
  write_exports()
        |
        +--> glean_golinks_export.json   (full API records, unchanged)
        +--> glean_golinks_export.csv    (one row per shortcut, one column per field)
```

Step by step:

1. **Load configuration.** `python-dotenv` reads `.env` beside the script; the
   two required variables are validated without ever printing their values.
2. **Paginate through the API.** Each request asks for 100 shortcuts. The
   response's `meta.cursor` is sent on the next request until
   `meta.hasNextPage` is `false`. The script aborts rather than silently
   producing a partial export if the API reports another page but omits the
   cursor, or if a cursor repeats.
3. **Write JSON.** All records are dumped as-is, so no API field is lost.
4. **Write CSV.** Column headers are the union of every field seen across all
   records, in first-seen order, so optional fields present on only some
   shortcuts still get a column. Nested values (objects and arrays) are
   serialized as JSON strings inside the cell. The file is UTF-8 with BOM so it
   opens cleanly in Excel.
5. **Report.** The exported count is compared with the API's `totalItemCount`.

## Output files

Both files are written next to the script.

| File | Contents |
| --- | --- |
| `glean_golinks_export.json` | Array of shortcut objects exactly as returned by the API |
| `glean_golinks_export.csv` | Flat table, one row per shortcut |

### CSV columns

The columns come straight from the API's `Shortcut` object. Which ones appear
depends on what the API returns for your instance; commonly populated fields are:

| Column | Description |
| --- | --- |
| `id` | Numeric shortcut ID |
| `inputAlias` | The text after `go/` as the user typed it (e.g. `eng-oncall`) |
| `alias` | Canonical alias with hyphens/underscores removed (e.g. `engoncall`) |
| `title` | Display title of the Go Link |
| `description` | Free-text description |
| `destinationUrl` | Where the link redirects |
| `urlTemplate` | Template for variable links (e.g. `https://jira.example.com/browse/{*}`) |
| `unlisted` | `True` if hidden from the directory, `False` if public |
| `isExternal` | `True` for shortcuts imported from an external Go Link tool |
| `viewPrefix` | Prefix shown to users, usually `go/` |
| `intermediateUrl` | Full `https://go/...` style redirect URL |
| `editUrl` | Link to the shortcut's edit page in Glean |
| `createTime` / `updateTime` | ISO 8601 timestamps |
| `createdBy` / `updatedBy` | JSON object describing the person |
| `destinationDocument` | JSON object for the Glean document at the destination, if indexed |
| `permissions` | JSON object with `write`/`read` flags |
| `roles` | JSON array of user roles (owner, editor, etc.) |
| `favoriteInfo` | JSON object indicating whether the admin has favorited it |

### Sample CSV

```csv
id,inputAlias,alias,title,description,destinationUrl,unlisted,isExternal,viewPrefix,createTime,updateTime,createdBy,permissions
1041,eng-oncall,engoncall,Engineering On-Call,Current on-call rotation,https://oncall.example.com/rotations/engineering,False,False,go/,2024-03-11T18:22:04Z,2025-09-02T15:40:51Z,"{""name"": ""Jane Doe"", ""obfuscatedId"": ""abc123""}","{""read"": true, ""write"": true}"
1077,payroll,payroll,Payroll Portal,,https://hr.example.com/payroll,False,False,go/,2024-04-02T09:05:33Z,2024-04-02T09:05:33Z,"{""name"": ""John Smith"", ""obfuscatedId"": ""def456""}","{""read"": true, ""write"": true}"
1203,secret-project,secretproject,Project Falcon,Internal only,https://docs.example.com/falcon,True,False,go/,2025-01-15T22:10:00Z,2025-06-30T11:02:17Z,"{""name"": ""Jane Doe"", ""obfuscatedId"": ""abc123""}","{""read"": true, ""write"": true}"
```

Note: the real export will typically contain more columns than this sample
(`urlTemplate`, `editUrl`, `destinationDocument`, `roles`, etc.), and empty
cells indicate the field was absent or `null` for that shortcut.

## Security notes

- The export contains destination URLs and author information that may be
  sensitive. Store and share the output files appropriately.
- The script never prints the API token. API error bodies are echoed to stderr
  to aid troubleshooting, but the `Authorization` header is not.
- `.env` should be excluded from version control.
