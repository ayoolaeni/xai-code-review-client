// Loads the signed-in user's profile card on the dashboard.

const profileName = document.getElementById("profile-name");
const profileRole = document.getElementById("profile-role");

async function fetchProfile(userId) {
  const response = await fetch(`/api/users/${userId}`);
  const data = await response.json();
  return data;
}

function roleLabel(role) {
  if (role == "admin") {
    return "Administrator";
  }
  if (role == "editor") {
    return "Editor";
  }
  return "Member";
}

async function showProfile(userId) {
  const profile = await fetchProfile(userId);
  profileName.textContent = profile.name;
  profileRole.textContent = roleLabel(profile.role);
}

showProfile(document.body.dataset.userId);
