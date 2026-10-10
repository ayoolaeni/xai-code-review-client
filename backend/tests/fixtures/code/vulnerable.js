const { exec } = require("child_process");

function showComment(comment) {
  const box = document.getElementById("comments");
  box.innerHTML = "<p>" + comment + "</p>";
}

function calculate(expression) {
  return eval(expression);
}

function convert(file) {
  exec(`convert ${file} out.png`, (err) => {
    if (err == null) {
      console.log("done");
    }
  });
}

module.exports = { showComment, calculate, convert };
