// Merges user preferences sent from the settings page into the stored profile.

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function deepMerge(target, source) {
  for (const key in source) {
    if (isPlainObject(source[key])) {
      if (!isPlainObject(target[key])) {
        target[key] = {};
      }
      deepMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

function updatePreferences(profile, submittedPreferences) {
  const updated = deepMerge({}, profile.preferences);
  deepMerge(updated, submittedPreferences);
  return { ...profile, preferences: updated };
}

module.exports = { deepMerge, updatePreferences };
