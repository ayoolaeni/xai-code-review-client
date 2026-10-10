// Evaluates spreadsheet-style formulas typed by users in the budget planner.

const express = require("express");

const router = express.Router();

function isFormula(text) {
  return typeof text === "string" && text.startsWith("=") && text.length <= 200;
}

function evaluateFormula(text) {
  const expression = text.slice(1);
  return eval(expression);
}

router.post("/budget/formula", express.json(), (req, res) => {
  const { formula } = req.body;
  if (!isFormula(formula)) {
    res.status(400).json({ error: "A formula must start with =" });
    return;
  }
  const value = evaluateFormula(formula);
  res.json({ formula, value });
});

module.exports = router;
