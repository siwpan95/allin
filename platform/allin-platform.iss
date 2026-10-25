; allin-platform 安装包（2026-08-27，评估文档 A 级第 1 项）
; 服务型：便携 Node v26.7.0 + 依赖 + registry 配置 + 桌面入口 + 可选开机自启
; 编译：ISCC.exe allin-platform.iss → installer\allin-platform-setup-1.0.0.exe
;
; 打包前置（_installer-src\stage 需先备好）：
;   1. 下载便携 Node：https://nodejs.org/dist/v26.7.0/node-v26.7.0-win-x64.zip
;      解压到 stage\node\（node.exe 同层）
;   2. 复制 apps/ packages/ registry/ scripts/ harness/ node_modules/（@allin/core 需为 packages/core 的实体副本）
;      以及 package.json / package-lock.json / start-platform.bat / LICENSE / README.md；data/ 建空目录
;   3. node_modules\.bin 可删（安装后不跑 npm 脚本，直接 node.exe 启动）
; 2026-09-24 对齐 DSH 形态：入口统一 start-platform.bat（PORT=0 临时端口 +
; 自动开浏览器，关闭窗口即释放端口），不再常驻 9000。
#define MyAppName "allin-platform 集成平台"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "siwpan"
#define MyAppNode "node\node.exe"
#define MyAppEntry "start-platform.bat"

[Setup]
AppId={{C4E1D2B0-9A51-4F8E-A3D7-ALLINPLATF01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\allin-platform
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=allin-platform-setup-1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\node\node.exe
UninstallDisplayName={#MyAppName}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "开机自启动平台门户（临时端口，按需启动）"; GroupDescription: "系统集成:"; Flags: unchecked

[Files]
Source: "_installer-src\stage\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "_precheck.out.log,_precheck.err.log"
Source: "_installer-src\stage\node\node.exe"; DestDir: "{app}\node"; Flags: ignoreversion uninsrestartdelete

[Icons]
Name: "{group}\{#MyAppName} 门户"; Filename: "{app}\{#MyAppNode}"; Parameters: """{app}\{#MyAppEntry}"""; WorkingDir: "{app}"
Name: "{group}\{#MyAppName} 配置审计"; Filename: "{app}\{#MyAppNode}"; Parameters: """{app}\scripts\check.mjs"""; WorkingDir: "{app}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppNode}"; Parameters: """{app}\{#MyAppEntry}"""; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppEntry}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppNode}"; Parameters: """{app}\{#MyAppEntry}"""; WorkingDir: "{app}"; Description: "立即启动 {#MyAppName} 门户"; Flags: nowait postinstall skipifsilent
