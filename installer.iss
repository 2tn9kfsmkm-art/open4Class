; ============================================================
;  ClassManager 安装包（Inno Setup 6）
;  安装到用户目录，不需要管理员权限
;
;  编译：  iscc /DAPPVERSION=0.40.0 installer.iss
;  未指定版本时用 0.0.0
; ============================================================

#ifndef APPVERSION
  #define APPVERSION "0.0.0"
#endif

#define APPNAME "班级管理系统"
#define APPEXE "ClassManager.exe"

[Setup]
AppId={{8F3A62C1-4B7E-4A55-9C2D-1A6B7E9F0C31}
AppName={#APPNAME}
AppVersion={#APPVERSION}
AppVerName={#APPNAME} {#APPVERSION}
AppPublisher=市西中学
DefaultDirName={localappdata}\ClassManager
DefaultGroupName={#APPNAME}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=ClassManager-Setup-{#APPVERSION}
SetupIconFile=resources\icon.ico
UninstallDisplayIcon={app}\{#APPEXE}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
Source: "build\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"
Name: "{group}\卸载 {#APPNAME}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#APPEXE}"; Description: "立即启动"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 只删程序目录；用户数据在 %APPDATA%\ClassManager，卸载不动它
Type: filesandordirs; Name: "{app}"

[Messages]
chinesesimplified.WelcomeLabel2=即将在您的电脑上安装 [name/ver]。%n%n数据会保存在 %APPDATA%\ClassManager，卸载本软件时不会删除这些数据。
