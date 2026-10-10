// Helper functions for the shopping cart on the checkout page.
// All prices are whole numbers of kobo (1/100 of a naira) to avoid rounding errors.

const VAT_PERCENT = 7.5;

function cartSubtotal(items) {
  return items.reduce((sum, item) => sum + item.priceKobo * item.quantity, 0);
}

function cartVat(items) {
  return Math.round((cartSubtotal(items) * VAT_PERCENT) / 100);
}

function cartTotal(items) {
  return cartSubtotal(items) + cartVat(items);
}

function addItem(items, product, quantity) {
  if (!Number.isInteger(quantity) || quantity <= 0) {
    throw new RangeError("Quantity must be a positive whole number.");
  }
  const existing = items.find((item) => item.id === product.id);
  if (existing) {
    return items.map((item) =>
      item.id === product.id ? { ...item, quantity: item.quantity + quantity } : item
    );
  }
  return [...items, { id: product.id, priceKobo: product.priceKobo, quantity }];
}

module.exports = { cartSubtotal, cartVat, cartTotal, addItem };
