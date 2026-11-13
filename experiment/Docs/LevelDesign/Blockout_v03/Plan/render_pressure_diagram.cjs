// Refresh PNG after running generate_pressure_diagram.py.
const path = require('node:path');
const sharp = require('C:/Users/21475/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const folder = __dirname;
sharp(path.join(folder, '敌阵高低差_平面与剖面.svg'))
  .png()
  .toFile(path.join(folder, '敌阵高低差_平面与剖面.png'))
  .then(() => process.stdout.write('PNG saved\n'))
  .catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
