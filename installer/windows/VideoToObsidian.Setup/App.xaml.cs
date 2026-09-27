using System.IO;
using System.Text.Json;
using System.Windows;

namespace VideoToObsidian.Setup;

public partial class App : Application
{
    protected override async void OnStartup(StartupEventArgs e)
    {
        if (e.Args.Length == 2 && e.Args[0] == "--verify-payload")
        {
            try
            {
                InstallationClient.WriteEmbeddedWheelVerification(e.Args[1]);
                Shutdown(0);
            }
            catch
            {
                Shutdown(1);
            }
            return;
        }
        if (e.Args.Length == 2 && e.Args[0] == "--prepare-machine")
        {
            var exitCode = 0;
            object report;
            try
            {
                await new InstallationClient().EnsureInstalledAsync(_ => { });
                report = new
                {
                    schema_version = 1,
                    ok = true,
                    contains_secrets = false,
                    paid_call_performed = false,
                };
            }
            catch (Exception exception)
            {
                exitCode = 1;
                report = new
                {
                    schema_version = 1,
                    ok = false,
                    error_type = exception.GetType().Name,
                    error = exception.Message,
                    contains_secrets = false,
                    paid_call_performed = false,
                };
            }
            var parent = Path.GetDirectoryName(Path.GetFullPath(e.Args[1]));
            if (!string.IsNullOrWhiteSpace(parent))
            {
                Directory.CreateDirectory(parent);
            }
            await File.WriteAllTextAsync(
                e.Args[1],
                JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true })
            );
            Shutdown(exitCode);
            return;
        }
        base.OnStartup(e);
    }
}
