import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/** Opens database connections for the order-processing service. */
public class V03DbConnector {
    private static final String DB_URL = "jdbc:postgresql://db.internal:5432/shop";
    private static final String DB_USER = "shop_app";
    private static final int VALIDATION_TIMEOUT_SECONDS = 2;

    public Connection open() throws SQLException {
        return DriverManager.getConnection(DB_URL, DB_USER, "Sh0pP@ssw0rd!2024");
    }

    public boolean isReachable() {
        try (Connection connection = open()) {
            return connection.isValid(VALIDATION_TIMEOUT_SECONDS);
        } catch (SQLException e) {
            return false;
        }
    }
}
