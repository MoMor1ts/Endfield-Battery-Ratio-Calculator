@echo off
chcp 936 >nul
cd /d "%~dp0"
echo ================================================
echo   Endfield Battery Calculator - build single exe
echo ================================================
echo.
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)
echo 打包工具: %PY%
echo 正在打包（resource 里的电池图片和 logo 会被打进 exe），请稍候...
echo.
rem 临时缓存放到系统 TEMP，避免项目里出现中文名的 build 子目录
"%PY%" -m PyInstaller --noconfirm --workpath "%TEMP%\endfield_battery_build" "endfield_battery.spec"
if errorlevel 1 (
    echo.
    echo [失败] 打包出错，请把上面的信息发给开发者。
) else (
    echo.
    echo [完成] 生成的 exe 在 dist 文件夹里，名字仍是「终末地电池计算.exe」。
)
echo.
pause
