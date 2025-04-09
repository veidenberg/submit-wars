import axios, { AxiosRequestConfig } from 'axios';
import { config } from '../config/config';

export class ApiService {
    protected baseUrl: string;
    protected apiToken: string;
    
    constructor(baseUrl: string, apiToken: string) {
        this.baseUrl = baseUrl;
        this.apiToken = apiToken;
    }
    
    protected async get<T>(endpoint: string, headers: Record<string, string> = {}): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;
        if (config.app.debug) console.log(`[DEBUG] GET request: ${url}`);
        
        try {
            const response = await axios.get(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...headers
                }
            });
            
            return response.data;
        } catch (error) {
            if (config.app.debug) console.error(`[DEBUG] Error in GET request to ${url}:`, error);
            throw error;
        }
    }
    
    protected async put<T>(endpoint: string, data: any, headers: Record<string, string> = {}): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;
        if (config.app.debug) console.log(`[DEBUG] PUT request: ${url}`);
        
        try {
            const response = await axios.put(url, data, {
                headers: {
                    'Content-Type': 'application/json',
                    ...headers
                }
            });
            
            return response.data;
        } catch (error) {
            if (config.app.debug) console.error(`[DEBUG] Error in PUT request to ${url}:`, error);
            throw error;
        }
    }
}
