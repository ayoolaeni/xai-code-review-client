import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.util.Base64;
import java.util.Map;

/** Restores a shopping cart that the browser sent back in a cookie. */
public class V04SessionReader {

    @SuppressWarnings("unchecked")
    public Map<String, Object> readCart(String cookieValue) throws IOException, ClassNotFoundException {
        byte[] data = Base64.getDecoder().decode(cookieValue);
        try (ObjectInputStream input = new ObjectInputStream(new ByteArrayInputStream(data))) {
            return (Map<String, Object>) input.readObject();
        }
    }

    public int itemCount(String cookieValue) throws IOException, ClassNotFoundException {
        Object items = readCart(cookieValue).get("items");
        return items instanceof java.util.List<?> list ? list.size() : 0;
    }
}
