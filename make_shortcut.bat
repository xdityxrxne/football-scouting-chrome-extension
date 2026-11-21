@echo off
rem Puts a "Player Extractor" shortcut on the Desktop that runs run.bat.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop = [Environment]::GetFolderPath('Desktop');" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Player Extractor.lnk'));" ^
  "$s.TargetPath = (Join-Path '%~dp0' 'run.bat');" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.IconLocation = 'shell32.dll,137';" ^
  "$s.Description = 'Player Extractor';" ^
  "$s.Save();" ^
  "Write-Host 'Shortcut created on the Desktop: Player Extractor'"
pause
