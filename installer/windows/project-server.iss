#ifndef Payload
  #error Payload is required
#endif
[Setup]
AppId={{86ABBE58-7896-4E93-9E83-815788699EFA}
AppName=BuildCostIQ 施工项目部服务端
AppVersion=0.8.0-rc9
LanguageDetectionMethod=none
ShowLanguageDialog=no
DefaultDirName={autopf}\BuildCostIQ
DisableDirPage=yes
DefaultGroupName=BuildCostIQ
OutputDir={#OutputDir}
OutputBaseFilename=BuildCostIQ-ProjectServer-v0.8.0-rc9-x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile={#Payload}\app\gui\static\sayelf-logo.ico
PrivilegesRequired=admin
Compression=lzma2/fast
SolidCompression=yes
UninstallDisplayName=BuildCostIQ 施工项目部服务端
UninstallDisplayIcon={app}\app\gui\static\sayelf-logo.ico
CloseApplications=no
[Languages]
Name: "chinesesimp"; MessagesFile: "{#InstallerLanguages}\ChineseSimplified.isl"
[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\打开 BuildCostIQ 造价工作台"; Filename: "http://localhost:8787/"; IconFilename: "{app}\app\gui\static\sayelf-logo.ico"
[Code]
var
  ProjectPage, AccountPage, StoragePage: TInputQueryWizardPage;
  Existing: Boolean;

function PSQuote(S: String): String;
begin
  StringChangeEx(S, '''', '''''', True);
  Result := '''' + S + '''';
end;

function JsonString(S: String): String; forward;

function IsProjectCodeValid(S: String): Boolean;
var I, C: Integer;
begin
  Result := (Length(S) >= 1) and (Length(S) <= 64);
  for I := 1 to Length(S) do begin
    C := Ord(S[I]);
    if not (((C >= 48) and (C <= 57)) or ((C >= 65) and (C <= 90)) or
      ((C >= 97) and (C <= 122)) or (C = 95) or (C = 45)) then Result := False;
  end;
end;

function RunConfig(Remove: Boolean): Boolean;
var Script, Params: String; Code: Integer; Shell, Proc: Variant;
begin
  Script := '& ' + PSQuote(ExpandConstant('{app}\configure.ps1')) + ' -InstallDir ' + PSQuote(ExpandConstant('{app}'));
  if Remove then Script := Script + ' -Remove';
  Params := 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "' + Script + '"';
  Shell := CreateOleObject('WScript.Shell');
  Proc := Shell.Exec(Params);
  if (not Remove) and (not Existing) then begin
    Proc.StdIn.Write('{"project_name":' + JsonString(ProjectPage.Values[0]) +
      ',"project_code":' + JsonString(ProjectPage.Values[1]) +
      ',"currency":' + JsonString(ProjectPage.Values[2]) +
      ',"timezone":' + JsonString(ProjectPage.Values[3]) +
      ',"username":' + JsonString(AccountPage.Values[0]) +
      ',"password":' + JsonString(AccountPage.Values[1]) +
      ',"data_root":' + JsonString(StoragePage.Values[0]) +
      ',"backup_root":' + JsonString(StoragePage.Values[1]) + '}');
  end;
  Proc.StdIn.Close;
  while Proc.Status = 0 do Sleep(100);
  Code := Proc.ExitCode;
  Result := Code = 0;
end;

function JsonString(S: String): String;
var I, C: Integer; Escaped: String;
begin
  StringChangeEx(S, '\', '\\', True);
  StringChangeEx(S, '"', '\"', True);
  StringChangeEx(S, #13, '\r', True);
  StringChangeEx(S, #10, '\n', True);
  StringChangeEx(S, #9, '\t', True);
  Escaped := '';
  for I := 1 to Length(S) do begin
    C := Ord(S[I]);
    if (C < 32) or (C > 126) then
      Escaped := Escaped + '\u' + Format('%.4x', [C])
    else Escaped := Escaped + S[I];
  end;
  Result := '"' + Escaped + '"';
end;

procedure InitializeWizard;
var Root: String;
begin
  Existing := FileExists(ExpandConstant('{commonappdata}\BuildCostIQ\server.json'));
  ProjectPage := CreateInputQueryPage(wpWelcome, '项目信息', '单个施工项目部', '请填写项目基本信息。');
  ProjectPage.Add('项目名称', False); ProjectPage.Add('项目编码（字母、数字、下划线或短横线）', False);
  ProjectPage.Add('货币代码（3位）', False); ProjectPage.Add('时区（IANA）', False);
  ProjectPage.Values[2] := 'CNY'; ProjectPage.Values[3] := 'Asia/Shanghai';
  AccountPage := CreateInputQueryPage(ProjectPage.ID, '管理员账户', '项目管理员', '请设置管理员登录信息，密码至少8位。');
  AccountPage.Add('管理员账号', False); AccountPage.Add('密码', True);
  StoragePage := CreateInputQueryPage(AccountPage.ID, '数据与备份', '数据目录和独立备份目录', '升级、修复或卸载不会删除这些目录。');
  StoragePage.Add('数据目录', False); StoragePage.Add('备份目录', False);
  if DirExists('D:\') then Root := 'D:\BuildCostIQ' else Root := ExpandConstant('{commonappdata}\BuildCostIQ');
  StoragePage.Values[0] := Root + '\Data'; StoragePage.Values[1] := Root + '\Backups';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := Existing and ((PageID=ProjectPage.ID) or (PageID=AccountPage.ID) or (PageID=StoragePage.ID));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var ErrorMessage: String;
begin
  Result := True;
  ErrorMessage := '';
  if Existing then Exit;
  if CurPageID=ProjectPage.ID then begin
    ProjectPage.Values[2] := Uppercase(Trim(ProjectPage.Values[2]));
    if Trim(ProjectPage.Values[0]) = '' then ErrorMessage := '请填写项目名称。'
    else if not IsProjectCodeValid(Trim(ProjectPage.Values[1])) then ErrorMessage := '项目编码需为1至64位英文字母、数字、下划线或短横线。'
    else if Length(ProjectPage.Values[2]) <> 3 then ErrorMessage := '货币代码需为3位英文字母，例如 CNY。'
    else if Trim(ProjectPage.Values[3]) = '' then ErrorMessage := '请填写 IANA 时区，例如 Asia/Shanghai。';
  end;
  if CurPageID=AccountPage.ID then begin
    if Trim(AccountPage.Values[0]) = '' then ErrorMessage := '请填写管理员账号。'
    else if Length(AccountPage.Values[1]) < 8 then ErrorMessage := '管理员密码至少8位，可含字母和符号。';
  end;
  if CurPageID=StoragePage.ID then begin
    if (Trim(StoragePage.Values[0]) = '') or (Trim(StoragePage.Values[1]) = '') then ErrorMessage := '请填写数据目录和备份目录。'
    else if CompareText(StoragePage.Values[0],StoragePage.Values[1]) = 0 then ErrorMessage := '数据目录和备份目录必须相互独立。';
  end;
  Result := ErrorMessage = '';
  if not Result then MsgBox(ErrorMessage, mbError, MB_OK);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Result := '';
  Code := 0;
  if RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\BuildCostIQProjectServer') and
    FileExists(ExpandConstant('{app}\BuildCostIQService.exe')) then
    if (not Exec(ExpandConstant('{app}\BuildCostIQService.exe'), 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code)) or (Code <> 0) then
      Result := '无法停止现有服务。';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var ErrorCode: Integer;
begin
  if CurStep=ssPostInstall then begin
    if not RunConfig(False) then RaiseException('配置或健康检查未通过，请查看日志：' + ExpandConstant('{commonappdata}\BuildCostIQ\logs\install.log'));
    if not ShellExecAsOriginalUser('open', 'http://localhost:8787/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode) then
      MsgBox('安装成功，但未能自动打开浏览器，请手动访问 http://localhost:8787/。', mbInformation, MB_OK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep=usUninstall then
    if not RunConfig(True) then RaiseException('服务移除失败；项目数据已保留。');
end;
