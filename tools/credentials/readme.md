.\gitee-credential.ps1 config          # 配置：写入 credential.helper → GCM + provider=generic（幂等）
.\gitee-credential.ps1 get             # 读取：显示 gitee.com 的用户名与令牌
.\gitee-credential.ps1 get -Clipboard  # 读取：不回显明文，直接复制到剪贴板（推荐）
.\gitee-credential.ps1 test            # 验证：调 Gitee /api/v5/user 确认令牌有效并显示账号


设计要点

不硬编码盘符：GCM 路径按 %USERPROFILE% 动态定位并自动选最新版本（铁律 5）；令牌本身不存在脚本里，随时可换新令牌无需改脚本。
读取链路：git credential fill → GCM → Windows 凭据管理器（DPAPI 加密），即 09-24 排查确认的正规链路。
安全边界：get 默认回显明文（提示勿截图/入仓），-Clipboard 则只进剪贴板；GCM 取凭据较慢，脚本内有 10~30 秒的预期提示。
编码处理：文件已写 UTF-8 BOM，避免 PowerShell 5.1 把中文注释读成乱码。
实测结果：config 写入后与现有 ~/.gitconfig 值完全一致（幂等验证通过）；test 以退出码 0 结束，令牌验证有效。