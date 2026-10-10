import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/** Calculates order totals with VAT for the checkout service. */
public final class V10PriceCalculator {
    private static final BigDecimal VAT_RATE = new BigDecimal("0.075");
    private static final int MONEY_SCALE = 2;

    private V10PriceCalculator() {
    }

    public static BigDecimal subtotal(List<BigDecimal> linePrices) {
        BigDecimal total = BigDecimal.ZERO;
        for (BigDecimal price : linePrices) {
            if (price.signum() < 0) {
                throw new IllegalArgumentException("Prices cannot be negative");
            }
            total = total.add(price);
        }
        return total.setScale(MONEY_SCALE, RoundingMode.HALF_UP);
    }

    public static BigDecimal vat(BigDecimal subtotal) {
        return subtotal.multiply(VAT_RATE).setScale(MONEY_SCALE, RoundingMode.HALF_UP);
    }

    public static BigDecimal total(List<BigDecimal> linePrices) {
        BigDecimal net = subtotal(linePrices);
        return net.add(vat(net));
    }
}
