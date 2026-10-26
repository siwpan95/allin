<#
.SYNOPSIS
    Gitee 凭据配置与令牌获取工具（本机自用）

.DESCRIPTION
    config  配置 git 全局 credential.helper 指向 GCM，并为 gitee.com 设 provider=generic（幂等，可重复执行）
    get     从 Windows 凭据管理器读取 gitee.com 令牌并显示（默认）
    get -Clipboard  不回显令牌，直接复制到剪贴板（更安全）
    test    调 Gitee API 验证令牌有效性，输出所属账号

.EXAMPLE
    .\gitee-credential.ps1 config
    .\gitee-credential.ps1 get
    .\gitee-credential.ps1 get -Clipboard
    .\gitee-credential.ps1 test

.NOTES
    - 令牌明文只进当前终端/剪贴板，脚本本身不存储任何密钥。
    - GCM 取凭据较慢（10~30 秒），首次调用请耐心等待。
    - 存储位置：Windows 凭据管理器（DPAPI 按当前用户加密），
      条目名 git:https://gitee.com 与 git:https://oauth2@gitee.com。
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('config', 'get', 'test')]
    [string]$Action = 'get',

    [switch]$Clipboard   # 仅 get 有效：不回显令牌，直接复制到剪贴板
)

$ErrorActionPreference = 'Stop'
$GiteeHost = 'gitee.com'

# ---------- 定位 GCM（不硬编码盘符，按用户目录动态解析） ----------
function Find-Gcm {
    $pattern = Join-Path $env:USERPROFILE '.workbuddy\binaries\PortableGit\versions\*\mingw64\bin\git-credential-manager.exe'
    $hit = Get-Item -Path $pattern -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $hit) {
        throw "未找到 git-credential-manager.exe（查找模式：$pattern）"
    }
    return $hit.FullName
}

# ---------- 从凭据管理器读取令牌（经 git credential fill） ----------
function Get-GiteeCred {
    Write-Host "正在读取 $GiteeHost 凭据（GCM 较慢，可能需要 10~30 秒）..."
    $stdinText = "protocol=https`nhost=$GiteeHost`n`n"
    $lines = $stdinText | & git credential fill 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "git credential fill 失败（exit=$LASTEXITCODE）"
    }
    $username = ($lines | Where-Object { $_ -like 'username=*' }) -replace '^username=', ''
    $token    = ($lines | Where-Object { $_ -like 'password=*' }) -replace '^password=', ''
    if (-not $token) {
        throw "未取到令牌：凭据管理器中可能还没有 $GiteeHost 条目（先手动 git push/pull 一次完成登录）"
    }
    [pscustomobject]@{ Username = $username; Token = $token }
}

# ---------- config：写入 git 全局配置（幂等） ----------
function Invoke-Config {
    $gcm = (Find-Gcm) -replace '\\', '/'
    & git config --global credential.helper ('!"{0}"' -f $gcm)
    & git config --global ("credential.https://{0}.provider" -f $GiteeHost) 'generic'
    Write-Host "已写入 ~/.gitconfig，当前生效配置："
    Write-Host ("  credential.helper = {0}" -f (& git config --global --get credential.helper))
    Write-Host ("  provider          = {0}" -f (& git config --global --get ("credential.https://{0}.provider" -f $GiteeHost)))
}

# ---------- get：输出或复制令牌 ----------
function Invoke-Get {
    $cred = Get-GiteeCred
    if ($Clipboard) {
        Set-Clipboard -Value $cred.Token
        Write-Host ("令牌已复制到剪贴板（账号: {0}，长度: {1} 字符）。用完建议清空剪贴板。" -f $cred.Username, $cred.Token.Length)
    }
    else {
        Write-Host "以下为明文令牌，请勿截图/转发/入仓："
        Write-Host ("  username: {0}" -f $cred.Username)
        Write-Host ("  token:    {0}" -f $cred.Token)
    }
}

# ---------- test：调 API 验证令牌 ----------
function Invoke-Test {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $cred = Get-GiteeCred
    try {
        $u = Invoke-RestMethod -Uri ("https://{0}/api/v5/user?access_token={1}" -f $GiteeHost, $cred.Token) -TimeoutSec 30
        Write-Host ("令牌有效。账号: {0}（姓名: {1}）" -f $u.login, $u.name)
    }
    catch {
        throw "令牌验证失败：$($_.Exception.Message)"
    }
}

switch ($Action) {
    'config' { Invoke-Config }
    'get'    { Invoke-Get }
    'test'   { Invoke-Test }
}
