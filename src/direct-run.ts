// Create this file to directly test loading of environment variables

import * as dotenv from 'dotenv';
import * as path from 'path';
import * as fs from 'fs';

// Try to locate the .env file
const envPath = path.resolve(__dirname, '../.env');
console.log(`Looking for .env file at: ${envPath}`);
console.log(`File exists: ${fs.existsSync(envPath)}`);

// Load the .env file
const result = dotenv.config({ path: envPath });
console.log('Dotenv config result:', result);

// Check if environment variables are loaded
console.log('Environment variables:');
console.log('TOGGL_API_TOKEN exists:', !!process.env.TOGGL_API_TOKEN);
console.log('TOGGL_WORKSPACE_ID exists:', !!process.env.TOGGL_WORKSPACE_ID);

// You can also verify the content of the file
try {
    const envContent = fs.readFileSync(envPath, 'utf8');
    console.log('.env file first few characters:', envContent.substring(0, 50) + '...');
} catch (error) {
    console.error('Error reading .env file:', error);
}
