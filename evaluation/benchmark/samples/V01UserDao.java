import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;

/** Data access for the customer newsletter: finds subscriber e-mail addresses. */
public class V01UserDao {
    private final Connection connection;

    public V01UserDao(Connection connection) {
        this.connection = connection;
    }

    public List<String> findEmailsByCountry(String country) throws SQLException {
        List<String> emails = new ArrayList<>();
        String sql = "SELECT email FROM users WHERE country = '" + country + "'";
        try (Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery(sql)) {
            while (rows.next()) {
                emails.add(rows.getString("email"));
            }
        }
        return emails;
    }
}
