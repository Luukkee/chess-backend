const path = require('path');
const webpack = require('webpack');
const dotenv = require('dotenv');

// Load environment variables from .env file
const env = dotenv.config().parsed;

// Convert the .env variables into a format that DefinePlugin can use
const envKeys = Object.keys(env).reduce((prev, next) => {
    prev[`process.env.${next}`] = JSON.stringify(env[next]);
    return prev;
}, {});

module.exports = {
  entry: path.resolve(__dirname, 'src/web/client/index.js'),
  output: {
    filename: 'main.js',
    path: path.resolve(__dirname, 'src/web/client/dist'),
  },
  mode: 'production',
  plugins: [
    new webpack.DefinePlugin({
      'process.env.REACT_APP_API_URL': JSON.stringify(process.env.REACT_APP_API_URL),
    }),
  ],

};