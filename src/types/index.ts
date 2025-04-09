export interface TimeRecord {
    id: number;
    description: string;
    start: string;
    end: string;
    duration: number;
    tags: string[];
    pid?: number; // Project ID from Toggl
    project?: string; // Project name
}

export interface ProjectMap {
    [key: number]: string;
}