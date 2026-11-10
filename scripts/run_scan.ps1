# Scheduled run (07:00, 13:00, 19:00): scan company feeds and remote boards for postings from the
# last 14 to 21 days, then let Claude score and draft any new fits headlessly.
# Registered with Task Scheduler by register_schedule.ps1. Never submits applications.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$scanDir = Join-Path $root "jobs\_scans"
New-Item -ItemType Directory -Force $scanDir | Out-Null
$log = Join-Path $scanDir "run_$stamp.log"
$draftLog = Join-Path $scanDir "drafting_$stamp.log"

"=== scan_jobs.py $stamp ===" | Out-File -FilePath $log -Encoding utf8
python scripts\scan_jobs.py --max-age 14 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"=== scan_boards.py $stamp ===" | Out-File -FilePath $log -Append -Encoding utf8
python scripts\scan_boards.py --max-age 21 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

# Mondays: grow the watchlist with new companies that hire in the candidate's country or worldwide.
if ((Get-Date).DayOfWeek -eq "Monday" -and (Get-Date).Hour -lt 10) {
    "=== discover_companies.py $stamp ===" | Out-File -FilePath $log -Append -Encoding utf8
    python scripts\discover_companies.py 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
}
# Keep jobs\_scans small: raw scan output older than 21 days is removed (seen.json is kept).
Get-ChildItem $scanDir -File | Where-Object { $_.Name -ne "seen.json" -and $_.LastWriteTime -lt (Get-Date).AddDays(-21) } | Remove-Item -Force

$prompt = "Run the job-scout routine on the new postings listed in ${log}. Score each with job-scoring; for passes create the job folder, resume (PDF, one page), score_and_gaps.md and application_answers.md; log everything in .claude/memory/application-log.md, and register each drafted role with python scripts/tracker.py add (status drafted). Read .claude/memory/search-playbook.md and the job-scoring score card first. For every drafted role scored 3.5 or higher follow .claude/skills/outreach/SKILL.md and write outreach.md (drafts only). Follow honesty-guardrails.md. Never submit anything. Do not ask questions. If nothing new passes, say so in one line."
claude -p $prompt --allowedTools "Read,Write,Edit,Glob,Grep,Bash,WebSearch" 2>&1 | Out-File -FilePath $draftLog -Append -Encoding utf8
