```json
{
  "name": "node-express-rest-api",
  "version": "1.0.0",
  "description": "A REST API built with Node.js, Express, and MongoDB.",
  "main": "src/server.js",
  "type": "module",
  "private": true,
  "scripts": {
    "start": "node src/server.js",
    "dev": "nodemon src/server.js",
    "test": "jest --coverage --verbose",
    "test:watch": "jest --watchAll --verbose"
  },
  "dependencies": {
    "bcryptjs": "^2.4.3",
    "cors": "^2.8.5",
    "dotenv": "^16.4.5",
    "express": "^4.19.2",
    "express-validator": "^7.1.0",
    "helmet": "^7.1.0",
    "http-status-codes": "^2.3.0",
    "jsonwebtoken": "^9.0.2",
    "mongoose": "^8.4.1",
    "morgan": "^1.10.0",
    "multer": "^1.4.5-lts.1",
    "nodemailer": "^6.9.13",
    "winston": "^3.13.0"
  },
  "devDependencies": {
    "eslint": "^8.57.0",
    "eslint-config-airbnb-base": "^15.0.0",
    "eslint-config-prettier": "^9.1.0",
    "eslint-plugin-import": "^2.29.1",
    "eslint-plugin-prettier": "^5.1.3",
    "jest": "^29.7.0",
    "mongodb-memory-server": "^9.3.0",
    "nodemon": "^3.1.3",
    "prettier": "^3.3.2",
    "supertest": "^7.0.0"
  },
  "engines": {
    "node": ">=18.0.0"
  },
  "author": "Your Name <your.email@example.com>",
  "license": "ISC"
}
```
