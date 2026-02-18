const express = require('express');
const path = require('path');

const app = express();

// Body parsing middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static folder for uploaded files
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// Configure EJS as the view engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Catch-all 404 handler
app.use((req, res, next) => {
  res.status(404).send('Not Found');
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
