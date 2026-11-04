@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "version=__VERSION__"
set "expectedPayloadHash=__PAYLOAD_SHA256__"
set "payload=%~dp0SKILLA-PC-payload.zip"

if not defined LOCALAPPDATA exit /b 10
if not exist "%payload%" exit /b 11

set "observedPayloadHash="
for /f "delims=" %%H in ('%SystemRoot%\System32\certutil.exe -hashfile "%payload%" SHA256 ^| %SystemRoot%\System32\findstr.exe /R /I "^[0-9A-F][0-9A-F]*$"') do if not defined observedPayloadHash set "observedPayloadHash=%%H"
if /I not "%observedPayloadHash%"=="%expectedPayloadHash%" exit /b 12

set "installParent=%LOCALAPPDATA%\SKILLA-PC"
set "destination=%installParent%\%version%"
set "resultFile=%installParent%\install-result-%version%.txt"

if not exist "%installParent%" mkdir "%installParent%"
if errorlevel 1 exit /b 14

call :write_result STARTED 0
if errorlevel 1 exit /b 19

if exist "%destination%\SKILLA.exe" (
  "%destination%\SKILLA.exe" verify-package "%destination%"
  if not errorlevel 1 (
    "%destination%\SKILLA.exe" install-start-menu "%destination%"
    if errorlevel 1 (
      call :write_result FAILED 20
      exit /b 20
    )
    call :write_result ALREADY_VERIFIED 0
    if errorlevel 1 exit /b 19
    echo SKILLA-PC is already installed and verified.
    exit /b 0
  )
)
if exist "%destination%" (
  call :write_result FAILED 13
  exit /b 13
)

set "staging=%installParent%\.installing-%RANDOM%%RANDOM%%RANDOM%"
if exist "%staging%" exit /b 15
mkdir "%staging%"
if errorlevel 1 exit /b 16

"%SystemRoot%\System32\tar.exe" -xf "%payload%" -C "%staging%"
if errorlevel 1 goto :fail_extract

if not exist "%staging%\SKILLA.exe" goto :fail_verify
"%staging%\SKILLA.exe" verify-package "%staging%"
if errorlevel 1 goto :fail_verify

move "%staging%" "%destination%" >nul
if errorlevel 1 goto :fail_move

"%destination%\SKILLA.exe" install-start-menu "%destination%"
if errorlevel 1 goto :fail_shortcut

call :write_result SUCCESS 0
if errorlevel 1 exit /b 19
echo Installed SKILLA-PC %version% to %destination%
echo Startup remains disabled. Provision the NIM credential separately.
exit /b 0

:fail_extract
set "failure=17"
goto :cleanup

:fail_verify
set "failure=18"
goto :cleanup

:fail_move
set "failure=19"
goto :cleanup

:fail_shortcut
set "failure=20"

:cleanup
if exist "%staging%" rmdir /s /q "%staging%"
call :write_result FAILED %failure%
if errorlevel 1 exit /b 19
exit /b %failure%

:write_result
> "%resultFile%" (
  echo schema_version=1
  echo version=%version%
  echo status=%~1
  echo code=%~2
)
if errorlevel 1 exit /b 1
exit /b 0
