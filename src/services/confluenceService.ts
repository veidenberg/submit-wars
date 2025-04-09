import axios from 'axios';
import { config } from '../config/config';

export class ConfluenceService {
    private confluenceBaseUrl: string;
    private confluenceApiToken: string;
    private confluenceSpaceKey: string;
    private confluencePageId: string;
    private confluenceUsername: string;
    private confluenceDisplayName: string;

    constructor(
        confluenceBaseUrl: string, 
        confluenceApiToken: string, 
        confluenceSpaceKey: string, 
        confluencePageId: string, 
        confluenceUsername: string,
        confluenceDisplayName?: string
    ) {
        this.confluenceBaseUrl = confluenceBaseUrl;
        this.confluenceApiToken = confluenceApiToken;
        this.confluenceSpaceKey = confluenceSpaceKey;
        this.confluencePageId = confluencePageId;
        this.confluenceUsername = confluenceUsername;
        this.confluenceDisplayName = confluenceDisplayName || confluenceUsername || 'Andres';
    }

    /**
     * Retrieves the existing page content for analysis
     */
    public async getExistingContent(): Promise<string> {
        const pageData = await this.getPageContent();
        return pageData.content;
    }
    
    /**
     * Checks if a specific week already has content for the current user
     */
    public hasWeekForUser(content: string, weekEndDate: string): boolean {
        const displayName = this.confluenceDisplayName;
        
        // Check for user heading under this week (h3 with display name)
        const userHeadingPattern = new RegExp(`<h2>w/e ${weekEndDate}</h2>.*?<h3>${displayName}</h3>`, 's');
        
        return userHeadingPattern.test(content);
    }

    public async postReport(formattedContent: string, dateRange?: { startDate: Date, endDate: Date }): Promise<void> {
        if (config.app.debug) console.log('[DEBUG] Creating Confluence content');
        
        // Get current page content first
        const currentPageData = await this.getPageContent();
        
        // Use provided date range or use current dates
        let weekInfo;
        if (dateRange) {
            // Extract month and date from the provided date range
            const endDate = dateRange.endDate;
            const month = endDate.toLocaleDateString('en-US', { month: 'long' });
            const weekEndDate = endDate.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' });
            weekInfo = { month, weekEndDate };
        } else {
            weekInfo = this.getCurrentWeekInfo();
        }
        
        // Prepare the new content and get status information
        const { updatedContent, status } = this.prepareUpdatedContent(
            currentPageData.content, 
            formattedContent,
            weekInfo
        );
        
        // Only update if content has changed
        if (updatedContent !== currentPageData.content) {
            await this.savePage(currentPageData.title, updatedContent, currentPageData.version);
            console.log(status);
        } else {
            if (config.app.debug) console.log(`No changes made to the Confluence page. ${status}`);
            else console.log(status);
        }
    }

    private async getPageContent(): Promise<{ content: string, title: string, version: number }> {
        const url = `${this.confluenceBaseUrl}/rest/api/content/${this.confluencePageId}?expand=body.storage,version`;
        if (config.app.debug) console.log(`[DEBUG] Fetching current page content: ${url}`);
        
        try {
            const response = await axios.get(url, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.confluenceApiToken}`
                }
            });
            
            return {
                content: response.data.body.storage.value,
                title: response.data.title,
                version: response.data.version.number
            };
        } catch (error) {
            if (config.app.debug) console.error('[DEBUG] Error fetching page content:', error);
            throw error;
        }
    }
    
    private async savePage(title: string, content: string, currentVersion: number): Promise<void> {
        const url = `${this.confluenceBaseUrl}/rest/api/content/${this.confluencePageId}`;
        if (config.app.debug) console.log(`[DEBUG] Updating Confluence page: ${url}`);
        
        try {
            const payload = {
                version: {
                    number: currentVersion + 1
                },
                title: title, // Keep the original page title
                type: 'page',
                body: {
                    storage: {
                        value: content,
                        representation: 'storage'
                    }
                }
            };
            
            const response = await axios.put(url, payload, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.confluenceApiToken}`
                }
            });

            if (config.app.debug) console.log(`[DEBUG] Confluence update response status: ${response.status}`);
            
            if (response.status !== 200) {
                throw new Error(`Failed to update Confluence page: ${response.status}`);
            }
        } catch (error) {
            if (config.app.debug) console.error('[DEBUG] Error updating Confluence page:', error);
            throw error;
        }
    }
    
    private prepareUpdatedContent(
        currentContent: string, 
        formattedContent: string,
        weekInfo: { month: string, weekEndDate: string }
    ): { updatedContent: string, status: string } {
        // Get week identifier and user info
        const { month, weekEndDate } = weekInfo;
        const displayName = this.confluenceDisplayName;
        
        // Check if the month heading already exists
        const monthHeadingPattern = new RegExp(`<h1>${month}</h1>`, 'i');
        
        // Check for week heading (h2 with w/e date)
        const weekHeadingPattern = new RegExp(`<h2>w/e ${weekEndDate}</h2>`, 'i');
        
        // Check for user heading under current week (h3 with display name)
        const userHeadingPattern = new RegExp(`<h2>w/e ${weekEndDate}</h2>.*?<h3>${displayName}</h3>`, 's');
        
        if (config.app.debug) {
            console.log(`[DEBUG] Checking for month: ${month}`);
            console.log(`[DEBUG] Checking for week: w/e ${weekEndDate}`);
            console.log(`[DEBUG] Checking for user: ${displayName}`);
        }
        
        // Case 1: This user's report already exists for this week
        if (userHeadingPattern.test(currentContent)) {
            if (config.app.debug) console.log('[DEBUG] This user already has a report for this week');
            return { 
                updatedContent: currentContent,
                status: `Report already exists for week ending ${weekEndDate}.`
            };
        }
        
        // Completely reorganize the page in proper chronological order
        if (config.app.debug) console.log('[DEBUG] Processing content to maintain chronological order');
        
        // Extract all existing month sections
        const monthSections = this.extractMonthSections(currentContent);
        
        // Add our new content to the appropriate section
        const updatedSections = this.addContentToMonthSections(monthSections, month, weekEndDate, displayName, formattedContent);
        
        // Reorder all sections and regenerate the entire page content
        const orderedContent = this.regenerateOrderedContent(updatedSections);
        
        // Determine the appropriate status message
        let status;
        if (userHeadingPattern.test(currentContent)) {
            status = `Report already exists for week ending ${weekEndDate}.`;
        } else if (weekHeadingPattern.test(currentContent)) {
            status = `Added report to existing week ending ${weekEndDate}.`;
        } else if (monthHeadingPattern.test(currentContent)) {
            status = `Added new week ending ${weekEndDate}.`;
        } else {
            status = `Added new month '${month}'.`;
        }
        
        return {
            updatedContent: orderedContent,
            status
        };
    }

    /**
     * Extracts all month sections from the content
     */
    private extractMonthSections(content: string): Map<string, string> {
        const monthSections = new Map<string, string>();
        const monthNames = ["January", "February", "March", "April", "May", "June", 
                            "July", "August", "September", "October", "November", "December"];
        
        // Extract each month section
        const monthPattern = /<h1>([A-Za-z]+)<\/h1>([\s\S]*?)(?=<h1>|$)/g;
        let match;
        
        while ((match = monthPattern.exec(content)) !== null) {
            const monthName = match[1];
            const monthContent = match[0];
            
            if (monthNames.includes(monthName)) {
                monthSections.set(monthName, monthContent);
                if (config.app.debug) console.log(`[DEBUG] Found existing month section: ${monthName}`);
            }
        }
        
        return monthSections;
    }

    /**
     * Adds the new content to the appropriate month section
     */
    private addContentToMonthSections(
        sections: Map<string, string>, 
        month: string, 
        weekEndDate: string, 
        displayName: string,
        formattedContent: string
    ): Map<string, string> {
        // Clone the sections map
        const updatedSections = new Map(sections);
        
        // Check if the month already exists
        if (updatedSections.has(month)) {
            const monthContent = updatedSections.get(month)!;
            
            // Check if week exists in this month
            const weekPattern = new RegExp(`<h2>w/e ${weekEndDate}</h2>`, 'i');
            const weekExists = weekPattern.test(monthContent);
            
            // Check if user exists for this week
            const userPattern = new RegExp(`<h2>w/e ${weekEndDate}</h2>.*?<h3>${displayName}</h3>`, 's');
            const userExists = userPattern.test(monthContent);
            
            if (userExists) {
                // No changes needed
                if (config.app.debug) console.log(`[DEBUG] User ${displayName} already exists for week ending ${weekEndDate}`);
                return updatedSections;
            } else if (weekExists) {
                // Add user to existing week
                if (config.app.debug) console.log(`[DEBUG] Adding user to existing week ending ${weekEndDate}`);
                
                // Split content at the week heading
                const parts = monthContent.split(weekPattern);
                if (parts.length < 2) {
                    if (config.app.debug) console.log(`[DEBUG] Week pattern found but couldn't split content properly`);
                    return updatedSections;
                }
                
                // Find where to insert the user section
                const afterWeekHeading = parts[1];
                const nextHeadingMatch = afterWeekHeading.match(/<h[123][^>]*>/i);
                
                let updatedMonthContent;
                if (nextHeadingMatch && nextHeadingMatch.index !== undefined) {
                    // Insert user section before the next heading
                    const insertPoint = nextHeadingMatch.index;
                    const userSection = this.createUserSection(displayName, formattedContent);
                    
                    updatedMonthContent = parts[0] + 
                                          `<h2>w/e ${weekEndDate}</h2>` + 
                                          afterWeekHeading.substring(0, insertPoint) + 
                                          userSection + 
                                          afterWeekHeading.substring(insertPoint);
                } else {
                    // No next heading, append to the end of the week section
                    const userSection = this.createUserSection(displayName, formattedContent);
                    updatedMonthContent = parts[0] + `<h2>w/e ${weekEndDate}</h2>` + afterWeekHeading + userSection;
                }
                
                updatedSections.set(month, updatedMonthContent);
            } else {
                // Add new week to existing month
                if (config.app.debug) console.log(`[DEBUG] Adding new week to existing month ${month}`);
                
                // Extract all week headings in this month to determine where to insert
                const weekHeadings: { date: Date, index: number }[] = [];
                const weekHeadingRegex = /<h2>w\/e (\d{2})\/(\d{2})<\/h2>/g;
                let weekMatch;
                
                while ((weekMatch = weekHeadingRegex.exec(monthContent)) !== null) {
                    try {
                        const day = parseInt(weekMatch[1]);
                        const monthNum = parseInt(weekMatch[2]) - 1; // JS months are 0-indexed
                        
                        // Create a date object for this week
                        const date = new Date();
                        date.setMonth(monthNum);
                        date.setDate(day);
                        
                        weekHeadings.push({
                            date,
                            index: weekMatch.index
                        });
                    } catch (e) {
                        if (config.app.debug) console.log('[DEBUG] Could not parse date:', weekMatch[1], weekMatch[2]);
                    }
                }
                
                // Parse the new week date
                const [newDay, newMonth] = weekEndDate.split('/').map(Number);
                const newDate = new Date();
                newDate.setMonth(newMonth - 1);
                newDate.setDate(newDay);
                
                // Create the week section to insert
                const weekSection = this.createWeekSection(weekEndDate, displayName, formattedContent);
                
                // Add after the h1 by default
                const h1EndIndex = monthContent.indexOf('</h1>') + 5;
                let insertPosition = h1EndIndex;
                
                // Sort weeks by date in reverse chronological order (newest first)
                weekHeadings.sort((a, b) => b.date.getTime() - a.date.getTime());
                
                // Find where to insert the new week to maintain reverse chronological order
                let inserted = false;
                for (let i = 0; i < weekHeadings.length; i++) {
                    const heading = weekHeadings[i];
                    
                    // If current week is older than our new week, insert before it
                    if (heading.date < newDate) {
                        insertPosition = heading.index;
                        inserted = true;
                        if (config.app.debug) console.log(`[DEBUG] Adding week ending ${weekEndDate} before week at index ${heading.index}`);
                        break;
                    }
                    
                    // If we're at the last heading and haven't inserted yet, 
                    // our new week is the oldest, so append after the last week
                    if (i === weekHeadings.length - 1 && !inserted) {
                        const nextHeadingMatch = monthContent.substring(heading.index + 20).match(/<h[12][^>]*>/i);
                        if (nextHeadingMatch && nextHeadingMatch.index !== undefined) {
                            insertPosition = heading.index + 20 + nextHeadingMatch.index;
                        } else {
                            // No next heading, append at the end of month content
                            insertPosition = monthContent.length;
                        }
                        if (config.app.debug) console.log(`[DEBUG] Adding week ending ${weekEndDate} at the end of month section`);
                    }
                }
                
                // If no weeks exist yet, insert right after h1
                if (weekHeadings.length === 0) {
                    if (config.app.debug) console.log(`[DEBUG] No existing weeks in month, adding after h1`);
                }
                
                const updatedMonthContent = monthContent.substring(0, insertPosition) + 
                                            weekSection + 
                                            monthContent.substring(insertPosition);
                
                updatedSections.set(month, updatedMonthContent);
            }
        } else {
            // Create a new month section
            if (config.app.debug) console.log(`[DEBUG] Creating new month section for ${month}`);
            const newSection = this.createFullSection(month, weekEndDate, displayName, formattedContent);
            updatedSections.set(month, newSection);
        }
        
        return updatedSections;
    }

    /**
     * Regenerates the content with all months in the correct order
     */
    private regenerateOrderedContent(sections: Map<string, string>): string {
        const monthNames = ["January", "February", "March", "April", "May", "June", 
                            "July", "August", "September", "October", "November", "December"];
        
        // Sort the sections by month (reverse chronological order)
        const months = Array.from(sections.keys());
        months.sort((a, b) => {
            const aIndex = monthNames.indexOf(a);
            const bIndex = monthNames.indexOf(b);
            return bIndex - aIndex; // Reverse chronological: December (11) to January (0)
        });
        
        // Construct the page content with months in the correct order
        let orderedContent = '';
        for (const month of months) {
            orderedContent += sections.get(month);
        }
        
        return orderedContent;
    }
    
    private createFullSection(month: string, weekEndDate: string, displayName: string, formattedContent: string): string {
        return `
<h1>${month}</h1>
<h2>w/e ${weekEndDate}</h2>
<h3>${displayName}</h3>
${formattedContent}

`;
    }
    
    private createWeekSection(weekEndDate: string, displayName: string, formattedContent: string): string {
        return `
<h2>w/e ${weekEndDate}</h2>
<h3>${displayName}</h3>
${formattedContent}

`;
    }
    
    private createUserSection(displayName: string, formattedContent: string): string {
        return `
<h3>${displayName}</h3>
${formattedContent}

`;
    }
    
    private getCurrentWeekInfo(): { month: string; weekEndDate: string } {
        const today = new Date();
        
        // Get most recent Friday
        const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
        let lastFriday = new Date(today);
        
        if (dayOfWeek === 6) { // Saturday
            lastFriday.setDate(today.getDate() - 1);
        } else if (dayOfWeek === 0) { // Sunday
            lastFriday.setDate(today.getDate() - 2);
        } else { // Monday through Friday
            lastFriday.setDate(today.getDate() - (dayOfWeek + 2));
        }
        
        // Get month name
        const monthFormat = new Intl.DateTimeFormat('en-US', { month: 'long' });
        const month = monthFormat.format(lastFriday);
        
        // Format for week ending date (DD/MM)
        const dayMonth = new Intl.DateTimeFormat('en-GB', { 
            day: '2-digit', 
            month: '2-digit'
        });
        const weekEndDate = dayMonth.format(lastFriday);
        
        return { month, weekEndDate };
    }
}