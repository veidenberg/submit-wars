import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const isVerboseMode = process.argv.includes('--verbose');

export const config = {
    toggl: {
        apiToken: process.env.TOGGL_API_TOKEN,
        workspaceId: process.env.TOGGL_WORKSPACE_ID,
        apiUrl: 'https://api.track.toggl.com/api/v9',
        reportApiUrl: 'https://api.track.toggl.com/reports/api/v2',
    },
    confluence: {
        username: process.env.CONFLUENCE_USERNAME,
        apiToken: process.env.CONFLUENCE_API_TOKEN,
        spaceKey: process.env.CONFLUENCE_SPACE_KEY,
        pageId: process.env.CONFLUENCE_PAGE_ID,
        baseUrl: process.env.CONFLUENCE_BASE_URL,
        displayName: process.env.CONFLUENCE_DISPLAY_NAME || process.env.CONFLUENCE_USERNAME || 'Andres',
    },
    app: {
        debug: isVerboseMode,
    }
};