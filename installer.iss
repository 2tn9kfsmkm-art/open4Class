; ============================================================
;  ClassManager 安装包（Inno Setup 6）
;
;  安装到用户目录，不需要管理员权限；
;  自带卸载器（「应用和功能」里可见），卸载时可选择是否删除班级数据。
;
;  编译：iscc /DAPPVERSION=0.40.0 installer.iss
; ============================================================

#ifndef APPVERSION
  #define APPVERSION "1.0.0-beta.1"
#endif

#define APPNAME      "班级管理系统"
#define APPPUBLISHER "市西中学"
#define APPEXE       "ClassManager.exe"
#define APPDATA_DIR  "ClassManager"

[Setup]
AppId={{8F3A62C1-4B7E-4A55-9C2D-1A6B7E9F0C31}
AppName={#APPNAME}
AppVersion={#APPVERSION}
AppVerName={#APPNAME} {#APPVERSION}
AppPublisher={#APPPUBLISHER}
AppPublisherURL=https://github.com/2tn9kfsmkm-art/open4Class
AppSupportURL=https://github.com/2tn9kfsmkm-art/open4Class/issues
AppUpdatesURL=https://github.com/2tn9kfsmkm-art/open4Class/releases
DefaultDirName={localappdata}\ClassManager
DefaultGroupName={#APPNAME}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=ClassManager-Setup-{#APPVERSION}
SetupIconFile=resources\icon.ico
UninstallDisplayName={#APPNAME}
UninstallDisplayIcon={app}\{#APPEXE}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0

; 程序运行中时由安装器提示关闭（用程序自己的单实例互斥体名）
AppMutex=Global\ClassManager-SingleInstance-v1
CloseApplications=yes
RestartApplications=no
RestartIfNeededByRun=no

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

; 卸载时自动删程序目录；数据目录由下面的脚本询问
[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Messages]
chinesesimplified.WelcomeLabel2=即将在您的电脑上安装 [name/ver]。%n%n程序安装到您的用户目录，不需要管理员权限。%n%n班级数据保存在 %APPDATA%\ClassManager，卸载时可以选择是否删除。

[Code]
{ 卸载时询问是否删除班级数据（默认保留，避免误删） }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Answer: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\{#APPDATA_DIR}');
    if DirExists(DataDir) then
    begin
      Answer := MsgBox('是否同时删除班级数据？' + #13#10 + #13#10 +
                       '位置：' + DataDir + #13#10 + #13#10 +
                       '选择「是」会删除名单、课表、值日、消息等内容，且无法恢复。' + #13#10 +
                       '选择「否」保留数据，以后重装可直接继续使用。',
                       mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
      if Answer = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
