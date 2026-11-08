<#
.SYNOPSIS
  allin 敏感材质排除策略（单一真相源 · tools/deploy）

.DESCRIPTION
  本文件是 backup-allin.ps1 / restore-allin.ps1 / test_restore_drill.ps1 三方
  **共同 dot-source 的单一真相源**：敏感材质排除清单只在此处定义一次，
  三方均通过 $AllinExcludedDirs / $AllinExcludedFiles 与 Get-AllinExcludeArgs 取用，
  避免清单硬编码在 4 处、对称性纯靠注释人工声明。新增敏感材质只需改这一处。

  口径来源（已读取仓库实际 .gitignore，别过度排除合法数据）：
  - 根 .gitignore 凭证段：*.token / *.key / *.pem / .env；
  - website/.gitignore：keys/ / *.key / *.pem / .env；
  - 治理明确项：seed-accounts.json（种子口令）、credentials.json（凭据）；
  - 明确的私钥/证书包：*.pfx / *.p12 / id_rsa / id_ed25519 / *.keystore。
  目录排除用 /XD（keys/），文件名/通配符用 /XF；robocopy /XF 支持通配符文件名
  （已实测 *.pem / *.key 等生效），无通配符名（.env / credentials.json）同样精确匹配。
  不纳入 *.json / *.log / *.txt / data 等可能是合法数据的模式，避免过度排除。

  keys/ 与种子口令走独立灾备通道 = website 的 npm run backup-key
  （0600 + 口令包 + 月度恢复演练），与 robocopy 主备份物理隔离。

  纪律：UTF-8 BOM、Windows PowerShell 5.1 兼容（无 6+ 语法）、零盘符字面量、零真实凭据。
#>

# 目录排除（/XD）：任何层级的 keys 目录都不进 robocopy 主备份
$AllinExcludedDirs = @('keys')

# 文件排除（/XF）：文件名或通配符模式，robocopy /XF 支持通配符
$AllinExcludedFiles = @(
  'seed-accounts.json'
  'credentials.json'
  '.env'
  '*.pem'
  '*.key'
  '*.token'
  '*.pfx'
  '*.p12'
  'id_rsa'
  'id_ed25519'
  '*.keystore'
)

function Get-AllinExcludeArgs {
  # 展开为 robocopy 参数序列：/XD <dirs> /XF <files>
  # backup / restore 用 /MIR @excludeArgs /NFL ... 调用；drill 用清单驱动断言。
  return (@('/XD') + $AllinExcludedDirs + @('/XF') + $AllinExcludedFiles)
}

# ---------------------------------------------------------------------------
# SHA-256（三方共用，2026-11-08 深度审核）
# 此前 backup / restore / drill 各自调用 Get-FileHash（Microsoft.PowerShell.Utility）。
# 由 cygwin/bash 以 -NoProfile 启动的 Windows PowerShell 5.1 不保证自动加载该模块，
# 实测 run_all_gates.sh 中报 CommandNotFoundException，整批恢复演练随之判失败。
# 改为 .NET BCL 流式计算：输出格式与 Get-FileHash -Algorithm SHA256 一致
# （大写十六进制、无分隔符），不依赖模块自动加载，PS 5.1 原生可用。
function Get-AllinSha256 {
  param([Parameter(Mandatory = $true)][string]$LiteralPath)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $stream = [System.IO.File]::OpenRead($LiteralPath)
    try {
      return ([System.BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '')
    } finally {
      $stream.Dispose()
    }
  } finally {
    $sha.Dispose()
  }
}
