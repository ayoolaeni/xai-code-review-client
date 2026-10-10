import java.io.File;
import java.io.IOException;
import java.nio.file.Files;

/** Returns sales reports (CSV files) that managers download from the back office. */
public class V05ReportDownload {
    private static final String REPORT_DIR = "/srv/reports/";

    public byte[] download(String reportName) throws IOException {
        if (!reportName.endsWith(".csv")) {
            throw new IllegalArgumentException("Only CSV reports can be downloaded");
        }
        File report = new File(REPORT_DIR + reportName);
        if (!report.isFile()) {
            throw new IOException("Report not found: " + reportName);
        }
        return Files.readAllBytes(report.toPath());
    }
}
