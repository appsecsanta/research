const express = require('express');
const { exec } = require('child_process');
const app = express();

app.use(express.json());

app.post('/api/ping', (req, res) => {
    const { hostname } = req.body;

    if (!hostname) {
        return res.status(400).json({ error: 'Hostname is required' });
    }

    exec(`ping -c 4 ${hostname}`, (error, stdout, stderr) => {
        if (error) {
            return res.status(500).json({ error: stderr });
        }
        res.json({ output: stdout });
    });
});

module.exports = app;
