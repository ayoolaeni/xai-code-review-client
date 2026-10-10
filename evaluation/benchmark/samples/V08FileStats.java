import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.Map;

/** Counts lines in the data files listed in the service configuration. */
public class V08FileStats {
    private final Map<String, String> configuredPaths;

    public V08FileStats(Map<String, String> configuredPaths) {
        this.configuredPaths = configuredPaths;
    }

    public int countLines(String key) throws IOException {
        String path = configuredPaths.get(key);
        BufferedReader reader = new BufferedReader(new FileReader(path.trim()));
        int lines = 0;
        while (reader.readLine() != null) {
            lines++;
        }
        return lines;
    }
}
