import { TimeRecord, ProjectMap } from '../types';
import { config } from '../config/config';

export function formatTimeRecords(timeRecords: TimeRecord[], projectMap: ProjectMap): string {
    if (config.app.debug) {
        console.log(`[DEBUG] Formatting ${timeRecords.length} time records`);
        console.log('[DEBUG] Project map contains', Object.keys(projectMap).length, 'projects');
    }
    
    if (!timeRecords || timeRecords.length === 0) {
        if (config.app.debug) console.log('[DEBUG] No time records found');
        return "No time records found for the last week.";
    }

    const projectGroups: { [key: string]: Set<string> } = {};
    
    timeRecords.forEach(record => {
        const projectName = record.pid && projectMap[record.pid] 
            ? projectMap[record.pid] 
            : 'No Project';
        
        if (!projectGroups[projectName]) {
            projectGroups[projectName] = new Set();
            if (config.app.debug) console.log(`[DEBUG] Created new project group: ${projectName}`);
        }
        
        if (record.description && record.description.trim() !== '') {
            projectGroups[projectName].add(record.description);
        }
    });

    if (config.app.debug) {
        console.log(`[DEBUG] Created ${Object.keys(projectGroups).length} project groups`);
        Object.keys(projectGroups).forEach(project => {
            console.log(`[DEBUG] Project ${project} has ${projectGroups[project].size} tasks`);
        });
    }

    let formattedOutput = '<ul>';
    const sortedProjects = Object.keys(projectGroups).sort();
    
    for (const projectName of sortedProjects) {
        formattedOutput += `<li>${projectName}`;
        
        const tasks = Array.from(projectGroups[projectName]).sort();
        if (tasks.length > 0) {
            formattedOutput += '<ul>';
            tasks.forEach(task => {
                formattedOutput += `<li>${task}</li>`;
            });
            formattedOutput += '</ul>';
        }
        
        formattedOutput += '</li>';
    }
    
    formattedOutput += '</ul>';
    
    if (config.app.debug) console.log('[DEBUG] Formatted output length:', formattedOutput.length);
    return formattedOutput;
}