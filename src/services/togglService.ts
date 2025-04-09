import { TimeRecord, ProjectMap } from '../types';
import { config } from '../config/config';

export class TogglService {
    private apiToken: string;
    private apiUrl: string;
    private reportApiUrl: string;
    private workspaceId: string;
    private earliestAllowedDate: Date | null = null;

    constructor(apiToken: string) {
        this.apiToken = apiToken;
        this.apiUrl = config.toggl.apiUrl;
        this.reportApiUrl = config.toggl.reportApiUrl;
        this.workspaceId = config.toggl.workspaceId || '';
        
        // Add validation to check if required values are present
        if (!this.apiToken) {
            console.error('[DEBUG] Toggl API token is missing');
        }
        
        if (!this.workspaceId) {
            console.error('[DEBUG] Toggl workspace ID is missing');
        }
    }

    async fetchTimeRecords(startDate: Date, endDate: Date): Promise<TimeRecord[]> {
        // Check if startDate is earlier than our known earliest allowed date
        if (this.earliestAllowedDate && startDate < this.earliestAllowedDate) {
            if (config.app.debug) {
                console.log(`[DEBUG] Start date ${startDate.toISOString()} is earlier than the earliest allowed date ${this.earliestAllowedDate.toISOString()}`);
                console.log('[DEBUG] Adjusting start date to the earliest allowed date');
            }
            startDate = new Date(this.earliestAllowedDate);
        }
        
        const url = `${this.apiUrl}/me/time_entries?start_date=${encodeURIComponent(startDate.toISOString())}&end_date=${encodeURIComponent(endDate.toISOString())}`;
        if (config.app.debug) console.log(`[DEBUG] Fetching time records from: ${url}`);
        
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Authorization': 'Basic ' + btoa(`${this.apiToken}:api_token`),
                    'Content-Type': 'application/json'
                }
            });
    
            if (!response.ok) {
                const errorText = await response.text();
                
                // Check if this is the "start_date must not be earlier than" error
                if (errorText.includes("start_date must not be earlier than")) {
                    const dateMatch = errorText.match(/than (\d{4}-\d{2}-\d{2})/);
                    if (dateMatch && dateMatch[1]) {
                        // Extract the earliest allowed date and store it
                        const earliestDate = new Date(dateMatch[1]);
                        this.earliestAllowedDate = earliestDate;
                        
                        if (config.app.debug) {
                            console.log(`[DEBUG] Toggl API restriction: earliest allowed date is ${earliestDate.toISOString()}`);
                            console.log(`[DEBUG] Retrying with adjusted start date`);
                        }
                        
                        // Try again with the corrected start date
                        return this.fetchTimeRecords(earliestDate, endDate);
                    }
                }
                
                if (config.app.debug) console.error(`[DEBUG] Error response from Toggl: ${errorText}`);
                throw new Error(`Failed to fetch time records from Toggl: ${response.status} ${response.statusText}`);
            }
    
            const data = await response.json();
            if (config.app.debug) console.log(`[DEBUG] Retrieved ${data.length} time entries from Toggl`);
            return data;
        } catch (error) {
            if (error instanceof Error && error.message.includes("Failed to fetch time records")) {
                throw error; // Re-throw our custom error
            }
            // For other errors (like network issues), create a new error
            if (config.app.debug) console.error('[DEBUG] Error fetching time records:', error);
            throw new Error(`Failed to fetch time records: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    async fetchProjects(): Promise<ProjectMap> {
        try {
            // Check if workspaceId exists before making the API call
            if (!this.workspaceId) {
                console.error('[DEBUG] Cannot fetch projects: Workspace ID is missing');
                return {};
            }
            
            const url = `${this.apiUrl}/workspaces/${this.workspaceId}/projects`;
            
            const authToken = Buffer.from(`${this.apiToken}:api_token`).toString('base64');
            
            if (config.app.debug) {
                console.log(`[DEBUG] Fetching projects from: ${url}`);
                console.log(`[DEBUG] Using workspace ID: ${this.workspaceId}`);
            }
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Authorization': `Basic ${authToken}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                const errorText = await response.text();
                if (config.app.debug) {
                    console.error(`[DEBUG] Error response from Toggl when fetching projects: ${errorText}`);
                    console.error(`[DEBUG] Response status: ${response.status}`);
                }
                
                return await this.fetchProjectsAlternative();
            }

            const projectMap: ProjectMap = {};
            const projects = await response.json();
            if (config.app.debug) console.log(`[DEBUG] Retrieved ${projects.length} projects from Toggl`);
            
            projects.forEach((project: any) => {
                projectMap[project.id] = project.name;
            });
            
            return projectMap;
        } catch (error) {
            if (config.app.debug) console.error('[DEBUG] Error fetching projects from Toggl:', error);
            throw error;
        }
    }
    
    private async fetchProjectsAlternative(): Promise<ProjectMap> {
        try {
            if (config.app.debug) console.log('[DEBUG] Trying alternative approach to fetch projects');
            const url = `${this.apiUrl}/me`;
            
            const authToken = Buffer.from(`${this.apiToken}:api_token`).toString('base64');
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Authorization': `Basic ${authToken}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                if (config.app.debug) console.error(`[DEBUG] Error with alternative approach: ${errorText}`);
                return {};
            }
            
            const userData = await response.json();
            if (config.app.debug) console.log('[DEBUG] User data received');
            
            const projectMap: ProjectMap = {};
            
            return projectMap;
        } catch (error) {
            if (config.app.debug) console.error('[DEBUG] Error in alternative project fetch:', error);
            return {};
        }
    }
}