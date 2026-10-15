# agent-toolkit 一行安装（Windows / PowerShell）
#   irm https://raw.githubusercontent.com/55200wq/agent-toolkit/main/install/install.ps1 | iex
#   带参数：$env:AGENT_TOOLKIT_ARGS="--project C:\my\proj --all"; irm ... | iex
$ErrorActionPreference = 'Stop'
$repo = if ($env:AGENT_TOOLKIT_REPO) { $env:AGENT_TOOLKIT_REPO } else { 'https://github.com/55200wq/agent-toolkit.git' }
$tmp = Join-Path $env:TEMP ("agent-toolkit-" + [guid]::NewGuid().ToString('N').Substring(0,8))
Write-Host "[agent-toolkit] 拉到临时目录：$tmp"
git clone --depth 1 $repo (Join-Path $tmp 'agent-toolkit') | Out-Null
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
$args = if ($env:AGENT_TOOLKIT_ARGS) { $env:AGENT_TOOLKIT_ARGS -split ' ' } else { @() }
& $py (Join-Path $tmp 'agent-toolkit/install/install.py') @args
Write-Host "[agent-toolkit] 完成 ✓（临时目录：$tmp，可自行删除）"
