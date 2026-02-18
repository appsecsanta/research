```json
{
  "name": "express-rest-api",
  "version": "1.0.0",
  "description": "Node.js Express REST API with MongoDB, JWT auth, file uploads, email, and testing",
  "main": "src/server.js",
  "scripts": {
    "start": "node src/server.js",
    "dev": "nodemon src/server.js",
    "test": "jest --coverage --detectOpenHandles",
    "test:watch": "jest --watch",
    "lint": "eslint src/",
    "lint:fix": "eslint src/ --fix"
  },
  "keywords": [
    "express",
    "rest-api",
    "mongodb",
    "jwt",
    "nodejs"
  ],
  "author": "",
  "license": "MIT",
  "dependencies": {
    "bcryptjs": "^2.4.3",
    "cors": "^2.8.5",
    "dotenv": "^16.4.5",
    "express": "^4.21.0",
    "express-rate-limit": "^7.4.0",
    "express-validator": "^7.2.0",
    "helmet": "^7.1.0",
    "joi": "^17.13.3",
    "jsonwebtoken": "^9.0.2",
    "mongodb": "^6.9.0",
    "mongoose": "^8.7.0",
    "morgan": "^1.10.0",
    "multer": "^1.4.5-lts.1",
    "nodemailer": "^6.9.15",
    "uuid": "^10.0.0"
  },
  "devDependencies": {
    "eslint": "^9.11.0",
    "jest": "^29.7.0",
    "nodemon": "^3.1.7",
    "supertest": "^7.0.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```
