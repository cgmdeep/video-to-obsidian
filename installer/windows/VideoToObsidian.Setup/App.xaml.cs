using System.IO;
using System.Text.Json;
using System.Windows;

namespace VideoToObsidian.Setup;

public partial class App : Application
{
    private const int InvalidArgumentsExitCode = 64;
    private const int InstallFailedExitCode = 20;
    private const int RepairFailedExitCode = 21;
    private const int UninstallFailedExitCode = 30;

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
            var resultPath = e.Args[1];
            var wasInstalled = new InstallationClient().IsInstalled;
            var operation = wasInstalled ? "repair" : "install";
            // A default uninstall preserves the user's private configuration.
            // Reinstallation must therefore reuse its Vault just like repair;
            // on a genuinely fresh machine this property falls back to default.
            var vaultPath = MachinePreparationClient.ConfiguredVaultPathOrDefault;
            try
            {
                WritePreparationReport(resultPath, new
                {
                    schema_version = 1,
                    operation,
                    status = "running",
                    phase = wasInstalled ? "正在开始修复…" : "正在开始首次准备…",
                    contains_secrets = false,
                    paid_call_performed = false,
                });
                await new MachinePreparationClient().PrepareAsync(
                    vaultPath,
                    MachinePreparationClient.DefaultWorkspacePath,
                    phase => WritePreparationReport(resultPath, new
                    {
                        schema_version = 1,
                        operation,
                        status = "running",
                        phase,
                        contains_secrets = false,
                        paid_call_performed = false,
                    })
                );
                report = new
                {
                    schema_version = 1,
                    operation,
                    ok = true,
                    status = "complete",
                    vault_created = Directory.Exists(vaultPath),
                    workspace_created = Directory.Exists(MachinePreparationClient.DefaultWorkspacePath),
                    contains_secrets = false,
                    paid_call_performed = false,
                };
            }
            catch (Exception exception)
            {
                exitCode = wasInstalled ? RepairFailedExitCode : InstallFailedExitCode;
                report = new
                {
                    schema_version = 1,
                    operation,
                    ok = false,
                    status = "failed",
                    error_code = wasInstalled ? "repair_failed" : "install_failed",
                    error_type = exception.GetType().Name,
                    error = exception.Message,
                    contains_secrets = false,
                    paid_call_performed = false,
                };
            }
            WritePreparationReport(resultPath, report);
            Shutdown(exitCode);
            return;
        }
        if (e.Args.Length is 2 or 3 && e.Args[0] == "--uninstall-machine")
        {
            var resultPath = e.Args[1];
            var removePrivateData = e.Args.Length == 3
                && e.Args[2] == "--remove-private-data";
            if (e.Args.Length == 3 && !removePrivateData)
            {
                WritePreparationReport(resultPath, new
                {
                    schema_version = 1,
                    operation = "uninstall",
                    ok = false,
                    status = "failed",
                    error_code = "invalid_arguments",
                    error = "未知的卸载参数。",
                    contains_secrets = false,
                    paid_call_performed = false,
                });
                Shutdown(InvalidArgumentsExitCode);
                return;
            }
            var operation = removePrivateData ? "private-uninstall" : "uninstall";
            try
            {
                WritePreparationReport(resultPath, new
                {
                    schema_version = 1,
                    operation,
                    status = "running",
                    phase = "正在开始安全卸载…",
                    contains_secrets = false,
                    paid_call_performed = false,
                });
                var result = await new UninstallationClient().UninstallAsync(
                    MachinePreparationClient.DefaultWorkspacePath,
                    removePrivateData,
                    phase => WritePreparationReport(resultPath, new
                    {
                        schema_version = 1,
                        operation,
                        status = "running",
                        phase,
                        contains_secrets = false,
                        paid_call_performed = false,
                    })
                );
                WritePreparationReport(resultPath, new
                {
                    schema_version = 1,
                    operation,
                    ok = true,
                    status = "complete",
                    core_removed = result.CoreRemoved,
                    managed_mcp_removed = result.ManagedMcpRemoved,
                    vault_preserved = result.VaultPreserved,
                    workspace_preserved = result.WorkspacePreserved,
                    firefox_profile_preserved = result.FirefoxProfilePreserved,
                    private_data_removed = result.PrivateDataRemoved,
                    contains_secrets = false,
                    paid_call_performed = false,
                });
                Shutdown(0);
            }
            catch (Exception exception)
            {
                WritePreparationReport(resultPath, new
                {
                    schema_version = 1,
                    operation,
                    ok = false,
                    status = "failed",
                    error_code = exception is UninstallationSafetyException
                        ? "uninstall_safety_check_failed"
                        : "uninstall_failed",
                    error_type = exception.GetType().Name,
                    error = exception.Message,
                    contains_secrets = false,
                    paid_call_performed = false,
                });
                Shutdown(UninstallFailedExitCode);
            }
            return;
        }
        if (e.Args.Length > 0)
        {
            Shutdown(InvalidArgumentsExitCode);
            return;
        }
        base.OnStartup(e);
    }

    private static void WritePreparationReport(string destination, object report)
    {
        var fullPath = Path.GetFullPath(destination);
        var parent = Path.GetDirectoryName(fullPath);
        if (!string.IsNullOrWhiteSpace(parent))
        {
            Directory.CreateDirectory(parent);
        }
        var temporary = fullPath + ".tmp";
        File.WriteAllText(
            temporary,
            JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true })
        );
        File.Move(temporary, fullPath, overwrite: true);
    }
}
