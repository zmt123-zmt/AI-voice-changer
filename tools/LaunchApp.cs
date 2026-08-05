// AI 变声器启动器：双击本 exe 启动应用（python -m app.main）
// 编译：在项目根目录运行 build_exe.cmd
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

        // 优先使用项目 .venv，否则系统 Python
        string python = Path.Combine(dir, ".venv", "Scripts", "python.exe");
        if (!File.Exists(python)) python = "python";

        var psi = new ProcessStartInfo();
        psi.FileName = python;
        psi.Arguments = "-m app.main";
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        psi.Environment["PYTHONIOENCODING"] = "utf-8";
        // 重定向输出到日志文件（winexe 无控制台，print 不会显示）
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;

        try
        {
            using (var p = Process.Start(psi))
            {
                string stdout = p.StandardOutput.ReadToEnd();
                string stderr = p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (p.ExitCode != 0)
                {
                    try
                    {
                        File.WriteAllText(logPath,
                            "[stdout]\n" + stdout + "\n[stderr]\n" + stderr,
                            Encoding.UTF8);
                    }
                    catch { }
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
