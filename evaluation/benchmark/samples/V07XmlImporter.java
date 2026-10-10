import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import org.w3c.dom.Document;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

/** Imports product names from the XML catalogue files uploaded by suppliers. */
public class V07XmlImporter {

    public List<String> importProductNames(InputStream xml)
            throws ParserConfigurationException, SAXException, IOException {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        DocumentBuilder builder = factory.newDocumentBuilder();
        Document document = builder.parse(xml);
        NodeList names = document.getElementsByTagName("name");
        List<String> result = new ArrayList<>();
        for (int i = 0; i < names.getLength(); i++) {
            result.add(names.item(i).getTextContent());
        }
        return result;
    }
}
