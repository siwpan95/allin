<#
.SYNOPSIS
    Tavily 凭据读取工具（本机自用）

.DESCRIPTION
    get              从凭据来源读取 Tavily API key 并回显（默认）
    get -Clipboard   不回显，直接复制到剪贴板（推荐）
    test             调 Tavily API 验证 key 有效性并显示额度

.NOTES
    - 令牌明文只进当前终端/剪贴板，**脚本本身不存储任何密钥**。
    - 不硬编码盘符：凭据来源按 %USERPROFILE% 与仓内路径动态定位。
    - 读取链路与 gitee-credential.ps1 同规：脚本只认「来源 + 键名」，
      换 key 无需改脚本。
    - Windows PowerShell 5.1 会把 UTF-8 无 BOM 的文件按本地代码页读成乱码，
      因此这里显式按 UTF-8 读取（与 g09 的纪律一致）。
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('get', 'test', 'where')]
    [string]$Action = 'get',

    [switch]$Clipboard   # 仅 get 有效：不回显，直接复制到剪贴板
)

$ErrorActionPreference = 'Stop'

#: 凭据文件里的服务名；值在紧随其后的第一个非空行。
$CredentialEntry = 'Tavily'

#: 值必须以此前缀开头，用来把真正的 key 与同段的说明文字区分开。
$ValuePrefix = 'tvly-'

# ---------- 定位凭据来源（不硬编码盘符） ----------
function Find-CredentialFile {
    # 按同一相对位置在所有可能的工作盘上找；候选由环境变量与常见布局生成，
    # 不写死任何一个盘符。
    $roots = @()
    if ($env:DSH_CREDENTIAL_DIR) { $roots += $env:DSH_CREDENTIAL_DIR }
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem).Name) {
        $roots += ('{0}:\凭据管理器' -f $drive)
    }
    foreach ($root in $roots) {
        $candidate = Join-Path $root '私人令牌.txt'
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    throw "未找到凭据文件：在候选目录中都没有「私人令牌.txt」（可用 `$env:DSH_CREDENTIAL_DIR 指定目录）"
}

# ---------- 读取指定条目的值（显式 UTF-8） ----------
function Get-CredentialValue {
    param([string]$Path, [string]$Entry, [string]$Prefix)

    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    $lines = $text -split "`r?`n"

    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i].Trim() -ne $Entry) { continue }
        for ($j = $i + 1; $j -lt $lines.Length; $j++) {
            $value = $lines[$j].Trim()
            if ($value -eq '') { continue }
            if ($value.StartsWith($Prefix)) { return $value }
            break   # 该段的第一行非空值不是 key，说明结构变了
        }
    }
    throw "未在凭据文件中找到「$Entry」条目（期望其后首个非空值以 '$Prefix' 开头）"
}

# ---------- get：输出或复制 ----------
function Invoke-Get {
    $path = Find-CredentialFile
    $token = Get-CredentialValue -Path $path -Entry $CredentialEntry -Prefix $ValuePrefix
    if ($Clipboard) {
        Set-Clipboard -Value $token
        Write-Host ('Tavily key 已复制到剪贴板（长度 {0} 字符，来源 {1}）。用完建议清空剪贴板。' -f $token.Length, $path)
    }
    else {
        Write-Host "以下为明文 key，请勿截图/转发/入仓："
        Write-Host ("  {0}" -f $token)
    }
}

# ---------- test：调 API 验证 ----------
function Invoke-Test {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $path = Find-CredentialFile
    $token = Get-CredentialValue -Path $path -Entry $CredentialEntry -Prefix $ValuePrefix
    $body = @{ query = 'DeepSeek Harness'; max_results = 1 } | ConvertTo-Json -Compress
    try {
        $r = Invoke-RestMethod -Method Post -Uri 'https://api.tavily.com/search' `
            -Headers @{ Authorization = "Bearer $token" } `
            -ContentType 'application/json; charset=utf-8' `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 30
        Write-Host ('key 有效。返回 {0} 条结果，用时 {1}s。' -f @($r.results).Count, $r.response_time)
    }
    catch {
        throw "key 验证失败：$($_.Exception.Message)"
    }
}

# ---------- where：只报来源位置 ----------
function Invoke-Where {
    $path = Find-CredentialFile
    $token = Get-CredentialValue -Path $path -Entry $CredentialEntry -Prefix $ValuePrefix
    Write-Host ('凭据来源：{0}' -f $path)
    Write-Host ('条目「{0}」：存在，长度 {1} 字符（不回显）' -f $CredentialEntry, $token.Length)
}

switch ($Action) {
    'get'   { Invoke-Get }
    'test'  { Invoke-Test }
    'where' { Invoke-Where }
}
