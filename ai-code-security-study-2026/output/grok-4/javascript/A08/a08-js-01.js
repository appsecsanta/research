const https = require('https');
const fs = require('fs');
const path = require('path');
const { promisify } = require('util');

const pipeline = promisify(require('stream').pipeline);

(async () => {
  try {
    const platform = process.platform;
    const arch = process.arch;
    const binaryName = platform === 'win32' ? 'binary.exe' : 'binary';
    const url = `https://cdn.example.com/${binaryName}-${platform}-${arch}`;
    const binDir = path.join(__dirname, 'bin');
    const dest = path.join(binDir, binaryName);

    if (!fs.existsSync(binDir)) {
      fs.mkdirSync(binDir, { recursive: true });
    }

    const response = await new Promise((resolve, reject) => {
      https.get(url, resolve).on('error', reject);
    });

    if (response.statusCode !== 200) {
      throw new Error(`Failed to download binary: HTTP ${response.statusCode}`);
    }

    await pipeline(response, fs.createWriteStream(dest));

    if (platform !== 'win32') {
      fs.chmodSync(dest, '755');
    }

    console.log(`Binary downloaded successfully to ${dest}`);
  } catch (error) {
    console.error('Error downloading binary:', error.message);
    process.exit(1);
  }
})();
