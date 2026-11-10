param([string]$Docx, [string]$Pdf)
# Converts a .docx to .pdf with Microsoft Word and prints the page count.
# Word hung opening files straight from the project folder on 2026-10-29, so the work happens in a temp folder
# and the PDF is copied back. Everything is guarded so a stuck Word cannot hang an unattended run.
$Docx = (Resolve-Path $Docx).Path
$Pdf = [System.IO.Path]::GetFullPath($Pdf)
$work = Join-Path $env:TEMP ("docx2pdf_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
$tmpDocx = Join-Path $work "in.docx"
$tmpPdf = Join-Path $work "out.pdf"
Copy-Item $Docx $tmpDocx
$worker = {
    param($d, $p)
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try {
        $doc = $word.Documents.Open($d, $false, $true, $false)
        "pages=" + $doc.ComputeStatistics(2)
        $doc.ExportAsFixedFormat($p, 17)
        $doc.Close($false)
    } finally {
        $word.Quit()
    }
}
$job = Start-Job -ScriptBlock $worker -ArgumentList $tmpDocx, $tmpPdf
if (Wait-Job $job -Timeout 90) {
    Receive-Job $job
    if (Test-Path $tmpPdf) { Copy-Item $tmpPdf $Pdf -Force }
} else {
    Stop-Job $job
    Write-Output "ERROR: Word did not finish within 90 seconds"
}
Remove-Job $job -Force
Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
