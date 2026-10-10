// Renders the comments section under each product page.

const commentList = document.getElementById("comment-list");
const commentForm = document.getElementById("comment-form");

function formatDate(isoString) {
  const date = new Date(isoString);
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function renderComment(comment) {
  const item = document.createElement("li");
  item.className = "comment";
  item.innerHTML = "<strong>" + comment.author + "</strong> <span>" + formatDate(comment.createdAt) + "</span><p>" + comment.text + "</p>";
  commentList.appendChild(item);
}

async function loadComments(productId) {
  const response = await fetch(`/api/products/${productId}/comments`);
  const comments = await response.json();
  commentList.textContent = "";
  comments.forEach(renderComment);
}

commentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = new FormData(commentForm).get("text");
  const response = await fetch(commentForm.action, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  renderComment(await response.json());
});

loadComments(commentForm.dataset.productId);
