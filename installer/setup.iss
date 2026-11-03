; Скрипт сборки инсталлятора Inno Setup 6 для PrintPDF
; Позволяет устанавливать программу без прав администратора (в AppData\Local\Programs\PrintPDF)

#define MyAppName "PrintPDF"
; Версия передаётся из build.bat (/DMyAppVersion=...), единый источник — core/version.py
#ifndef MyAppVersion
  #error Версия не задана: собирайте установщик через build.bat (он берёт её из core/version.py)
#endif
#define MyAppPublisher "PrintPDF Team"
#define MyAppExeName "PrintPDF.exe"
#define MyAppIcon "..\autocad_to_pdf_icon.ico"

[Setup]
; Уникальный GUID приложения для корректного обновления поверх старой версии
AppId={{8B8A61D2-1F44-4F96-857A-3F4EEA6CB345}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=PrintPDF_Setup_v{#MyAppVersion}
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; Установка не требует прав администратора (ставится любому инженеру без обращения к сисадмину)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Автоматическое закрытие запущенной копии перед обновлением
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Копируем скомпилированное приложение из папки dist\PrintPDF
Source: "..\dist\PrintPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.py,*.pdb,*.git*"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
