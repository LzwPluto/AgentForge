; ==============================================================================
; AgentForge (智铸) - Inno Setup 现代化 Windows 安装包构建脚本
; 官方网站: https://github.com/your-username/AgentForge
; 适用平台: Windows 10 / Windows 11 (x64)
; ==============================================================================

#define MyAppName "AgentForge"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AgentForge Team"
#define MyAppURL "https://github.com/your-username/AgentForge"
#define MyAppExeName "AgentForge.exe"
#define MySourceDir "dist\AgentForge"

[Setup]
; 基础应用信息
AppId={{E58A322C-4A3C-432D-9B8A-A47E53D8C019}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 安装路径与目录设置
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=output
OutputBaseFilename=AgentForge_v{#MyAppVersion}_Windows_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; 现代视觉界面与高压缩率
WizardStyle=modern
WizardSizePercent=110
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 卸载清理设置
UninstallFilesDir={app}\uninstall

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 主程序及所有依赖文件夹 (直接打包 PyInstaller 编译出的 dist\AgentForge)
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 配置文件如果目标电脑已有则不强制覆盖，防止覆盖用户的 API 密钥
Source: "{#MySourceDir}\agentforge_config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 安装完成后允许用户勾选立即运行 AgentForge
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// 自定义卸载提示：询问是否保留用户的历史协同会话数据与沙箱工作区
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox('是否同时删除所有历史协同会话记录 (history) 与沙箱文件 (测试软件)？' #13#10 #13#10 '点击 [否] 将为您保留这些创作数据。', mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{app}\history'), True, True, True);
      DelTree(ExpandConstant('{app}\测试软件'), True, True, True);
      DelTree(ExpandConstant('{app}\sandbox_env'), True, True, True);
    end;
  end;
end;
