// AI 变声器启动器：双击本 exe 启动应用（python -m app.main）
// 编译：在项目根目录运行 build_exe.cmd
//
// 修复历史（2026-08-06）：
//   旧实现 `p.StandardOutput.ReadToEnd()` 会阻塞到子进程退出，stderr 管道(默认仅 4KB)
//   从未被排空 → RVC 加载 hubert 时 fairseq 日志(>4KB)写满管道 → python 线程永久阻塞
//   （表现为"声音转换一直停在转换中"）。
//   新实现：stdout/stderr 用 Begin*ReadLine 异步持续排空，管道永不写满。
//
// 修复历史（2026-08-08）：
//   旧实现 psi.FileName=python.exe + psi.Arguments="-m app.main"（lpApplicationName 方式）
//   启动 .venv python 时，venv launcher（python.exe）会把执行转发给 pyvenv.cfg 的
//   home 解释器（系统 Python311），产生双进程：一个 .venv 空壳（不加载 python311.dll，
//   CPU 0 / 内存 4MB）等待 + 一个系统 python 真身跑 app。双实例浪费资源且行为诡异。
//   （cm/ /c 包装、删 executable 字段等方法均不彻底，且影响 run.bat 等其他启动方式。）
//   最终方案：直接读 .venv\pyvenv.cfg 的 home 字段拿系统解释器，设 PYTHONPATH 指向
//   .venv\Lib\site-packages 跑 app——单进程、包版本与 .venv 一致、与系统 python 兼容。
//   注意：这也解释了"为什么系统 python 能显示窗口"——launcher 转发时就是这么干的。
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

class LaunchApp
{
    [STAThread]
    static void Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string logPath = Path.Combine(dir, "app_launch.log");

        // 优先使用项目 .venv：读 pyvenv.cfg 的 home 拿基础解释器，PYTHONPATH 指到 venv 包
        string python = "python";
        string pythonPath = "";
        string venvPy = Path.Combine(dir, ".venv", "Scripts", "python.exe");
        if (File.Exists(venvPy))
        {
            string cfg = Path.Combine(dir, ".venv", "pyvenv.cfg");
            if (File.Exists(cfg))
            {
                foreach (string raw in File.ReadAllLines(cfg))
                {
                    string line = raw.Trim();
                    if (line.StartsWith("home =", StringComparison.OrdinalIgnoreCase))
                    {
                        string home = line.Substring(6).Trim().TrimEnd('\\');
                        if (home.Length > 0)
                        {
                            python = Path.Combine(home, "python.exe");
                            pythonPath = Path.Combine(dir, ".venv", "Lib", "site-packages");
                        }
                        break;
                    }
                }
            }
        }

        var psi = new ProcessStartInfo();
        psi.FileName = python;
        psi.Arguments = "-m app.main";
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        psi.Environment["PYTHONIOENCODING"] = "utf-8";
        if (!string.IsNullOrEmpty(pythonPath))
        {
            psi.Environment["PYTHONPATH"] = pythonPath;
        }
        // 重定向输出到日志文件（winexe 无控制台，print 不会显示）
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;

        try
        {
            using (var p = Process.Start(psi))
            {
                // 关键：stdout 与 stderr 必须同时持续排空（异步事件），
                // 否则任一管道(Windows 匿名管道默认 4KB)被写满后，
                // 子进程写日志的线程会永久阻塞，导致"一直转换中"。
                var sbOut = new StringBuilder();
                var sbErr = new StringBuilder();
                p.OutputDataReceived += (s, e) =>
                {
                    if (e.Data != null)
                    {
                        lock (sbOut) { sbOut.AppendLine(e.Data); }
                    }
                };
                p.ErrorDataReceived += (s, e) =>
                {
                    if (e.Data != null)
                    {
                        lock (sbErr) { sbErr.AppendLine(e.Data); }
                    }
                };
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                p.WaitForExit();
                // 第二次 WaitForExit 确保异步输出事件全部处理完毕（.NET 文档要求）
                p.WaitForExit();

                try
                {
                    string stdout, stderr;
                    lock (sbOut) { stdout = sbOut.ToString(); }
                    lock (sbErr) { stderr = sbErr.ToString(); }
                    File.WriteAllText(logPath,
                        "[stdout]\n" + stdout + "\n[stderr]\n" + stderr,
                        Encoding.UTF8);
                }
                catch { }

                if (p.ExitCode != 0)
                {
                    MessageBox.Show(
                        "应用异常退出（退出码 " + p.ExitCode + "）。\n" +
                        "日志已写入 " + logPath + "。\n" +
                        "或改用 run.bat 启动查看控制台输出。",
                        "AI 变声器",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                }
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "启动失败：" + ex.Message + "\n\n" +
                "请确认已安装 Python（3.10+）并已安装依赖（setup.ps1 或 pip install -r requirements.txt）。",
                "AI 变声器",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}
