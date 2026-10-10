import java.io.IOException;
import java.util.concurrent.TimeUnit;

/** Creates compressed backups of customer data folders on request from the admin panel. */
public class V02BackupService {
    private static final String BACKUP_DIR = "/var/backups/shop";
    private static final long TIMEOUT_MINUTES = 10;

    public boolean backupFolder(String folderName) throws IOException, InterruptedException {
        String command = "tar -czf " + BACKUP_DIR + "/" + folderName + ".tgz /srv/data/" + folderName;
        Process process = Runtime.getRuntime().exec(command);
        boolean finished = process.waitFor(TIMEOUT_MINUTES, TimeUnit.MINUTES);
        if (!finished) {
            process.destroyForcibly();
            return false;
        }
        return process.exitValue() == 0;
    }
}
