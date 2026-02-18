const fs = require('fs');
const { exec } = require('child_process');

const manifestPath = process.argv[2];

if (!manifestPath) {
  console.error('Please provide the path to the build manifest JSON file.');
  process.exit(1);
}

fs.readFile(manifestPath, 'utf8', (err, data) => {
  if (err) {
    console.error(`Error reading manifest file: ${err.message}`);
    process.exit(1);
  }

  const manifest = JSON.parse(data);

  if (!Array.isArray(manifest)) {
    console.error('Manifest file should contain an array of build steps.');
    process.exit(1);
  }

  const executeCommands = async () => {
    for (const step of manifest) {
      if (!step.command) {
        console.error(`Missing command in step: ${JSON.stringify(step)}`);
        continue;
      }

      console.log(`Executing step: ${step.step || 'Unknown'}`);
      console.log(`Command: ${step.command}`);

      try {
        await new Promise((resolve, reject) => {
          exec(step.command, (error, stdout, stderr) => {
            if (error) {
              console.error(`Error executing command: ${error.message}`);
              reject(error);
              return;
            }

            if (stdout) {
              console.log(stdout);
            }

            if (stderr) {
              console.error(stderr);
            }

            resolve();
          });
        });
      } catch (error) {
        console.error(`Step failed: ${step.step || 'Unknown'}`);
        process.exit(1);
      }
    }

    console.log('All steps completed successfully.');
  };

  executeCommands();
});
