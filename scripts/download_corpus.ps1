param(
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $candidate = Resolve-Path (Join-Path $PSScriptRoot "..")
    if (-not (Test-Path (Join-Path $candidate "pyproject.toml"))) {
        throw "Could not infer the repository root. Place this script under <repo>\scripts or pass -ProjectRoot explicitly."
    }
    $ProjectRoot = $candidate.Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

$TargetRoot = Join-Path $ProjectRoot "data\raw\phase2_5"
New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot "data\phase2_5\manifest.yaml") -Destination (Join-Path $TargetRoot "manifest.yaml") -Force

$Headers = @{
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ChinaPolicyRAG/0.1"
}

$Sources = @(
    @{ File = "cn_genai_interim_measures_2023.html"; Url = "https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm" },
    @{ File = "cn_network_data_security_regulation_2024.html"; Url = "https://app.www.gov.cn/govdata/gov/202409/30/520076/article.html" },
    @{ File = "cn_digital_economy_14th_fyp_2021.html"; Url = "https://www.miit.gov.cn/xwdt/szyw/art/2022/art_4ecc233a663b44329d0863e60b51192b.html" },
    @{ File = "cn_intelligent_manufacturing_14th_fyp_2021.pdf"; Url = "https://www.miit.gov.cn/cms_files/filemanager/1226211233/attach/20226/95c25b0b936d49f1995bd8771599d18a.pdf" },
    @{ File = "cn_foreign_investment_negative_list_2024.pdf"; Url = "https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/202409/P020240907514493057643.pdf" },
    @{ File = "cn_foreign_investment_action_plan_2025.html"; Url = "https://www.mofcom.gov.cn/zcfb/zgdwjjmywg/art/2025/art_4a3fe49da8854e60ba50b51950e1429d.html" },
    @{ File = "eu_ai_act_2024_en.pdf"; Url = "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng/pdf" },
    @{ File = "eu_data_act_2023_en.pdf"; Url = "https://eur-lex.europa.eu/eli/reg/2023/2854/oj/eng/pdf" },
    @{ File = "eu_chips_act_2023_en.pdf"; Url = "https://eur-lex.europa.eu/eli/reg/2023/1781/oj/eng/pdf" }
)

$Results = @()
$Failed = @()

foreach ($Source in $Sources) {
    $Destination = Join-Path $TargetRoot $Source.File
    $Temporary = "$Destination.part"
    Write-Host "Downloading $($Source.File)..."

    try {
        if (Test-Path $Temporary) { Remove-Item $Temporary -Force }
        Invoke-WebRequest -Uri $Source.Url -OutFile $Temporary -Headers $Headers -MaximumRedirection 10

        $Bytes = [System.IO.File]::ReadAllBytes($Temporary)
        if ($Bytes.Length -lt 500) {
            throw "Downloaded payload is unexpectedly small: $($Bytes.Length) bytes."
        }

        if ($Source.File.ToLowerInvariant().EndsWith(".pdf")) {
            $Prefix = [System.Text.Encoding]::ASCII.GetString($Bytes[0..3])
            if ($Prefix -ne "%PDF") {
                throw "Expected PDF but received a different payload."
            }
        } else {
            $PreviewLength = [Math]::Min($Bytes.Length, 20000)
            $Preview = [System.Text.Encoding]::UTF8.GetString($Bytes, 0, $PreviewLength)
            if ($Preview -match "(?i)verify that you.?re not a robot|captcha|access denied|javascript is disabled") {
                throw "Likely anti-bot or access-denied page."
            }
        }

        Move-Item -Path $Temporary -Destination $Destination -Force
        $Hash = (Get-FileHash -Algorithm SHA256 -Path $Destination).Hash.ToLowerInvariant()

        $Results += [pscustomobject]@{
            file = $Source.File
            url = $Source.Url
            path = $Destination
            bytes = $Bytes.Length
            sha256 = $Hash
            status = "downloaded"
        }
        Write-Host "  OK: $($Source.File)"
    }
    catch {
        if (Test-Path $Temporary) { Remove-Item $Temporary -Force }
        if (Test-Path $Destination) { Remove-Item $Destination -Force }
        $Failed += [pscustomobject]@{
            file = $Source.File
            url = $Source.Url
            error = $_.Exception.Message
        }
        Write-Warning "  FAILED: $($Source.File) -- $($_.Exception.Message)"
    }
}

$Report = [pscustomobject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    project_root = $ProjectRoot
    target_root = $TargetRoot
    expected_count = $Sources.Count
    downloaded_count = $Results.Count
    failed_count = $Failed.Count
    downloaded = $Results
    failed = $Failed
}

$ReportPath = Join-Path $TargetRoot "download_report.json"
$Report | ConvertTo-Json -Depth 8 | Set-Content -Path $ReportPath -Encoding utf8

Write-Host ""
Write-Host "Downloaded $($Results.Count) of $($Sources.Count) sources."
Write-Host "Report: $ReportPath"

if ($Failed.Count -gt 0) {
    Write-Warning "Some sources require manual download. Use the URLs in download_report.json or source_catalog.yaml."
    exit 2
}

exit 0
