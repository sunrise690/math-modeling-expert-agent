using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Windows.Forms;

namespace TongGaoTeXLauncher
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            string directory = AppDomain.CurrentDomain.BaseDirectory;
            string desktopExe = Path.Combine(directory, "Qilintex.exe");
            string serverBundle = Path.Combine(directory, "resources", "server", "bundle.cjs");

            if (!File.Exists(desktopExe) || !File.Exists(serverBundle))
            {
                MessageBox.Show("应用文件不完整，请重新解压整个 Qilintex 文件夹。", "Qilintex", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            string dataDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Qilintex",
                "server-data"
            );
            Directory.CreateDirectory(dataDirectory);

            Process server = null;
            try
            {
                ProcessStartInfo serverInfo = new ProcessStartInfo(desktopExe, Quote(serverBundle));
                serverInfo.UseShellExecute = false;
                serverInfo.CreateNoWindow = true;
                serverInfo.WindowStyle = ProcessWindowStyle.Hidden;
                serverInfo.EnvironmentVariables["ELECTRON_RUN_AS_NODE"] = "1";
                serverInfo.EnvironmentVariables["NODE_ENV"] = "production";
                serverInfo.EnvironmentVariables["ALLOW_DEV_LOGIN"] = "true";
                serverInfo.EnvironmentVariables["DATA_DIR"] = dataDirectory;
                serverInfo.EnvironmentVariables["CLIENT_URL"] = "file://";
                server = Process.Start(serverInfo);

                Thread.Sleep(500);
                ProcessStartInfo desktopInfo = new ProcessStartInfo(desktopExe);
                desktopInfo.UseShellExecute = true;
                Process desktop = Process.Start(desktopInfo);
                if (desktop != null) desktop.WaitForExit();
            }
            catch (Exception error)
            {
                MessageBox.Show("启动失败：" + error.Message, "Qilintex", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                try
                {
                    if (server != null && !server.HasExited) server.Kill();
                }
                catch { }
            }
        }

        private static string Quote(string value)
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }
    }
}
