@echo off
chcp 65001 > nul

:: BatchGotAdmin (Request Admin Privileges)
:-------------------------------------
REM --> Check for permissions
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' ( echo Requesting administrative privileges... & goto UACPrompt ) else ( goto gotAdmin )
:UACPrompt
echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
"%temp%\getadmin.vbs" & del "%temp%\getadmin.vbs" & exit /B
:gotAdmin
if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
pushd "%CD%" & CD /D "%~dp0"
:--------------------------------------

echo.
echo =======================================================
echo   Clash Auto SpeedTest Task Setup (Final Version - Debug Pause)
echo =======================================================
echo This script will create/update the task using the template file.
echo.

REM --- 配置 ---
set TASK_NAME="Clash_Auto_SpeedTest"
set XML_TEMPLATE_FILE="%~dp0clash_task_template.xml"

REM --- 检查 XML 模板文件是否存在 ---
echo Checking for XML template file: %XML_TEMPLATE_FILE%
dir %XML_TEMPLATE_FILE% > nul 2>&1
if errorlevel 1 (
    echo Error: File check FAILED using 'dir' command. File not found or inaccessible.
    echo Path checked: %XML_TEMPLATE_FILE%
    echo Please double-check the file exists with the exact name and was saved with UTF-16 LE encoding.
    pause
    exit /b 1
) else (
    echo OK: File check SUCCEEDED using 'dir' command. File exists.
)
echo Press any key to proceed with task creation...
pause
echo.

REM --- 使用 XML 文件创建/更新计划任务 ---
echo Creating/Updating task %TASK_NAME% from XML template...
schtasks /create /F /XML %XML_TEMPLATE_FILE% /TN %TASK_NAME%

REM --- !! 在 schtasks 命令之后立刻暂停 !! ---
echo.
echo schtasks command has been executed. Press any key to check result/continue...
pause
REM --- !! 结束暂停 !! ---

REM --- 检查创建结果 ---
if %errorlevel% EQU 0 (
    echo.
    echo Task %TASK_NAME% created/updated successfully! (Based on errorlevel)
    echo It is scheduled to run daily at 08:00, 12:00, and 18:00.
    echo.
    echo You can verify the task in Windows Task Scheduler.
) else (
    echo.
    echo Error: Task creation likely failed. Errorlevel: %errorlevel%
    echo Check any messages logged just before the pause above.
    echo Possible reasons: XML file format error (ensure UTF-16 LE), permission issues, task name conflict, Task Scheduler service stopped.
)

echo.
echo Setup finished. Press any key to exit.
pause > nul
exit /b