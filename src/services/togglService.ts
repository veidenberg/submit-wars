import { TimeRecord, ProjectMap } from '../types';
import { config } from '../config/config';
import { ApiService } from './apiService';

export class TogglService extends ApiService {
    private reportApiUrl: string;
    private workspaceId: string;
    private earliestAllowedDate: Date | null = null;

    constructor(apiToken: string) {
        super(config.toggl.apiUrl, apiToken);
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

    // Create custom headers for Toggl Basic Auth
    private getTogglHeaders(): Record<string, string> {
        const authToken = Buffer.from(`${this.apiToken}:api_token`).toString('base64');
        return {
            'Authorization': `Basic ${authToken}`,
            'Content-Type': 'application/json'
        };
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
        
        const endpoint = `/me/time_entries?start_date=${encodeURIComponent(startDate.toISOString())}&end_date=${encodeURIComponent(endDate.toISOString())}`;
        
        try {
            const timeRecords = await this.get<TimeRecord[]>(endpoint, this.getTogglHeaders());
            if (config.app.debug) console.log(`[DEBUG] Retrieved ${timeRecords.length} time entries from Toggl`);
            return timeRecords;
        } catch (error) {
            // Check if this is the "start_date must not be earlier than" error
            const errorMessage = error instanceof Error ? error.message : String(error);
            
            if (errorMessage.includes("start_date must not be earlier than")) {
                const dateMatch = errorMessage.match(/than (\d{4}-\d{2}-\d{2})/);
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
            
            throw new Error(`Failed to fetch time records: ${errorMessage}`);
        }
    }

    async fetchProjects(): Promise<ProjectMap> {
        try {
            // Check if workspaceId exists before making the API call
            if (!this.workspaceId) {
                console.error('[DEBUG] Cannot fetch projects: Workspace ID is missing');
                return {};
            }
            
            const endpoint = `/workspaces/${this.workspaceId}/projects`;
            
            if (config.app.debug) {
                console.log(`[DEBUG] Fetching projects from: ${this.baseUrl}${endpoint}`);
                console.log(`[DEBUG] Using workspace ID: ${this.workspaceId}`);
            }
            
            try {
                const projects = await this.get<any[]>(endpoint, this.getTogglHeaders());
                if (config.app.debug) console.log(`[DEBUG] Retrieved ${projects.length} projects from Toggl`);
                
                const projectMap: ProjectMap = {};
                projects.forEach((project: any) => {
                    projectMap[project.id] = project.name;
                });
                
                return projectMap;
            } catch (error) {
                if (config.app.debug) {
                    console.error('[DEBUG] Error fetching projects from Toggl:', error);
                }
                return await this.fetchProjectsAlternative();
            }
        } catch (error) {
            if (config.app.debug) console.error('[DEBUG] Error fetching projects from Toggl:', error);
            throw error;
        }
    }
    
    private async fetchProjectsAlternative(): Promise<ProjectMap> {
        try {
            if (config.app.debug) console.log('[DEBUG] Trying alternative approach to fetch projects');
            const endpoint = `/me`;
            
            try {
                const userData = await this.get<any>(endpoint, this.getTogglHeaders());
                if (config.app.debug) console.log('[DEBUG] User data received');
                
                const projectMap: ProjectMap = {};
                
                return projectMap;
            } catch (error) {
                if (config.app.debug) console.error('[DEBUG] Error with alternative approach:', error);
                return {};
            }
        } catch (error) {
            if (config.app.debug) console.error('[DEBUG] Error in alternative project fetch:', error);
            return {};
        }
    }
}