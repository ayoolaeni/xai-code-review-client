// Order history API for the customer account page.

const express = require("express");
const { pool } = require("./db");

const router = express.Router();

async function findOrdersForCustomer(customerId, status) {
  const sql = "SELECT id, total, status, created_at FROM orders WHERE customer_id = " + customerId + " AND status = '" + status + "'";
  const result = await pool.query(sql);
  return result.rows;
}

router.get("/customers/:id/orders", async (req, res, next) => {
  try {
    const orders = await findOrdersForCustomer(req.params.id, req.query.status || "paid");
    res.json({ orders });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
