import java.io.FileInputStream;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

public class Vulnerable {
    public ResultSet find(Connection conn, String name) throws Exception {
        Statement stmt = conn.createStatement();
        String sql = "SELECT * FROM users WHERE name = '" + name + "'";
        return stmt.executeQuery(sql);
    }

    public int firstByte(String path) {
        try {
            FileInputStream in = new FileInputStream(path);
            return in.read();
        } catch (Exception e) {
        }
        return -1;
    }
}
