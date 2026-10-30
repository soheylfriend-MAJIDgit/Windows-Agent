$ErrorActionPreference = 'Stop'
$work = Join-Path $env:TEMP 'Windows-Agent-Setup'
$installer = Join-Path $work 'vc_redist.x64.exe'
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
    if (-not (Test-Path $installer) -or (Get-Item $installer).Length -lt 1000000) {
        Write-Host 'Downloading the official Microsoft Visual C++ x64 runtime...'
        Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $installer -UseBasicParsing
    }
    if ((Get-Item $installer).Length -lt 1000000) { throw 'Downloaded installer is unexpectedly small.' }
    $signature = Get-AuthenticodeSignature -FilePath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
        throw 'The downloaded file does not have a valid Microsoft Authenticode signature.'
    }
    Write-Host 'Microsoft Authenticode signature verified.'
    Write-Host 'Starting the Microsoft installer. Windows may request administrator approval.'
    $p = Start-Process -FilePath $installer -ArgumentList '/install', '/quiet', '/norestart' -Verb RunAs -Wait -PassThru
    if ($p.ExitCode -eq 3010) {
        Write-Host 'The Microsoft runtime requires a Windows restart before Paddle can load.'
        exit 3010
    }
    if ($p.ExitCode -ne 0) { throw "Microsoft installer returned exit code $($p.ExitCode)." }
    Write-Host 'Microsoft Visual C++ x64 runtime installed.'
    exit 0
}
catch {
    Write-Error $_
    exit 1
}
finally {
    Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
}
