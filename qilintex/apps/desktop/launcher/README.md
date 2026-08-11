# Windows 本地启动器

该启动器仅用于本地解包版兜底：它用同一个 Electron 可执行文件的 Node 模式启动内置协作服务，再启动桌面窗口，并在桌面窗口退出后结束服务进程。标准 NSIS/portable 构建会直接使用 `main.mjs` 的内置服务启动逻辑。

本地编译命令：

```powershell
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe /reference:System.Windows.Forms.dll /out:'release\win-unpacked\Qilintex 启动器.exe' 'apps\desktop\launcher\Program.cs'
```
