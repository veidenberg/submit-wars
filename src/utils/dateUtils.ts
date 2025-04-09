import { config } from '../config/config';

/**
 * Gets the date range for the last full work week (Monday through Friday)
 * This will always return the most recently completed week ending on Friday
 */
export function getLastWeekDates(): { startDate: Date; endDate: Date } {
    const today = new Date();
    const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
    
    // Calculate the most recent Friday
    let lastFriday = new Date(today);
    
    // If today is Saturday (6) or Sunday (0), we're already past Friday, adjust back to previous Friday
    if (dayOfWeek === 6) { // Saturday
        lastFriday.setDate(today.getDate() - 1);
    } else if (dayOfWeek === 0) { // Sunday
        lastFriday.setDate(today.getDate() - 2);
    } else { // Monday through Friday
        lastFriday.setDate(today.getDate() - (dayOfWeek + 2));
    }
    
    // Set to end of Friday (23:59:59)
    lastFriday.setHours(23, 59, 59, 999);
    
    // Calculate Monday of that week (4 days before Friday)
    const mondayOfLastWeek = new Date(lastFriday);
    mondayOfLastWeek.setDate(lastFriday.getDate() - 4);
    // Set to start of Monday (00:00:00)
    mondayOfLastWeek.setHours(0, 0, 0, 0);
    
    if (config.app.debug) {
        console.log(`[DEBUG] Last full work week: ${mondayOfLastWeek.toDateString()} to ${lastFriday.toDateString()}`);
    }
    
    return {
        startDate: mondayOfLastWeek,
        endDate: lastFriday
    };
}

/**
 * Gets all weeks in the current year, from January 1st to current date
 * Each week ends on Friday
 */
export function getAllWeeksInYear(): Array<{ startDate: Date; endDate: Date }> {
    const weeks: Array<{ startDate: Date; endDate: Date }> = [];
    const today = new Date();
    const currentYear = today.getFullYear();
    
    // Start from first day of the year
    const startDate = new Date(currentYear, 0, 1); // January 1st
    startDate.setHours(0, 0, 0, 0);
    
    // Find the first Friday
    let currentDate = new Date(startDate);
    const dayOfWeek = currentDate.getDay(); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
    
    // If not already a Friday, move to the first Friday
    if (dayOfWeek !== 5) { // 5 = Friday
        currentDate.setDate(currentDate.getDate() + ((5 - dayOfWeek + 7) % 7));
    }
    
    // Set to end of day for Fridays
    currentDate.setHours(23, 59, 59, 999);
    
    // Keep generating weeks until we reach the current date
    while (currentDate <= today) {
        // Create the week
        const weekEndDate = new Date(currentDate);
        const weekStartDate = new Date(weekEndDate);
        weekStartDate.setDate(weekEndDate.getDate() - 4); // Monday is 4 days before Friday
        weekStartDate.setHours(0, 0, 0, 0);
        
        weeks.push({
            startDate: new Date(weekStartDate),
            endDate: new Date(weekEndDate)
        });
        
        // Move to next Friday
        currentDate.setDate(currentDate.getDate() + 7);
    }
    
    if (config.app.debug) {
        console.log(`[DEBUG] Generated ${weeks.length} weeks for ${currentYear}`);
        weeks.forEach((week, index) => {
            console.log(`[DEBUG] Week ${index + 1}: ${week.startDate.toDateString()} to ${week.endDate.toDateString()}`);
        });
    }
    
    return weeks;
}