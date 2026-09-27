using System.Windows;

namespace VideoToObsidian.Setup;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
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
        base.OnStartup(e);
    }
}
