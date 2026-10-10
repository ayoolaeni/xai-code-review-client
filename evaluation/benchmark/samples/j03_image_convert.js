// Converts uploaded product photos to thumbnails using ImageMagick.

const { exec } = require("child_process");
const path = require("path");

const UPLOAD_DIR = "/srv/uploads";
const THUMB_DIR = "/srv/thumbnails";

function thumbnailName(fileName) {
  const base = path.basename(fileName, path.extname(fileName));
  return `${base}-thumb.png`;
}

function createThumbnail(fileName, width, callback) {
  const source = path.join(UPLOAD_DIR, path.basename(fileName));
  const target = path.join(THUMB_DIR, thumbnailName(fileName));
  exec(`convert ${source} -resize ${width}x ${target}`, (error) => {
    if (error) {
      callback(error);
      return;
    }
    callback(null, target);
  });
}

module.exports = { createThumbnail };
