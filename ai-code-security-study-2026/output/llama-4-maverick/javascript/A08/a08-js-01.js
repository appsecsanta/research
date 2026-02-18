const fs = require('fs');
const path = require('path');
const https = require('https');
const os = require('os');
const { promisify } = require('util');

const pipeline = promisify(require('stream').pipeline);

const CDN_URL = 'https://cdn.example.com/binaries';
const BINARY_NAME = 'my-binary';
const BIN_DIR = path.join(__dirname, 'bin');

async function downloadBinary() {
  const platform = os.platform();
  const arch = os.arch();
  const binaryUrl = `${CDN_URL}/${BINARY_NAME}-${platform}-${arch}`;

  if (!fs.existsSync(BIN_DIR)) {
    fs.mkdirSync(BIN_DIR, { recursive: true });
  }

  const binaryPath = path.join(BIN_DIR, BINARY_NAME);

  try {
    await pipeline(
      https.get(binaryUrl),
      fs.createWriteStream(binaryPath)
    );
    fs.chmodSync(binaryPath, 0o755);
    console.log(`Downloaded ${BINARY_NAME} to ${BIN_DIR}`);
  } catch (error) {
    console.error(`Failed to download ${BINARY_NAME}: ${error.message}`);
    process.exit(1);
  }
}

downloadBinary();
