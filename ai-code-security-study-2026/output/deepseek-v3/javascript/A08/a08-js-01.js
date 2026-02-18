```json
{
  "scripts": {
    "postinstall": "node -e \"const fs = require('fs'); const https = require('https'); const path = require('path'); const os = require('os'); const platform = os.platform(); const arch = os.arch(); const cdnUrl = `https://cdn.example.com/binaries/${platform}-${arch}/binary-name`; const binDir = path.join(__dirname, 'bin'); const binaryPath = path.join(binDir, 'binary-name'); if (!fs.existsSync(binDir)) fs.mkdirSync(binDir); const file = fs.createWriteStream(binaryPath); https.get(cdnUrl, response => { response.pipe(file); file.on('finish', () => { file.close(); fs.chmodSync(binaryPath, 0o755); console.log('Binary downloaded successfully.'); }); }).on('error', err => { fs.unlinkSync(binaryPath); console.error('Error downloading binary:', err); });\""
  }
}
```
