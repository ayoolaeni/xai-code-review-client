// Serves downloadable product manuals for the support site.

const express = require("express");
const path = require("path");

const app = express();
const MANUALS_DIR = path.join(__dirname, "manuals");

app.get("/manuals/:fileName", (req, res) => {
  const fileName = req.params.fileName;
  if (!fileName.endsWith(".pdf")) {
    res.status(400).send("Only PDF manuals can be downloaded.");
    return;
  }
  res.sendFile(path.join(MANUALS_DIR, fileName));
});

app.get("/health", (req, res) => {
  res.json({ status: "ok" });
});

app.listen(process.env.PORT || 3000);
