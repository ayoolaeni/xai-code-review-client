import java.io.FileWriter;
import java.io.IOException;
import java.util.List;

/** Builds the CSV export of the monthly order report. */
public class V09CsvBuilder {

    public String buildCsv(List<String[]> rows) {
        String csv = "";
        for (String[] row : rows) {
            csv += String.join(",", row) + "\n";
        }
        return csv;
    }

    public void save(List<String[]> rows, String fileName) {
        try (FileWriter writer = new FileWriter(fileName)) {
            writer.write(buildCsv(rows));
        } catch (IOException e) {
        }
    }
}
