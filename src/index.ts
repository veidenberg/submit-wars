import dotenv from 'dotenv';
import path from 'path';

// Load environment variables before importing anything else
dotenv.config({ path: path.resolve(__dirname, '../.env') });

import { TogglService } from './services/togglService';
import { ConfluenceService } from './services/confluenceService';
import { getAllWeeksInYear, getLastWeekDates } from './utils/dateUtils';
import { formatTimeRecords } from './utils/formatUtils';
import { config } from './config/config';
import { ProjectMap } from './types'; // Add this import statement

// Debug logging function
function debugLog(message: string, data?: any): void {
  if (config.app.debug) {
    console.log(`[DEBUG] ${message}`);
    if (data) {
      console.log(JSON.stringify(data, null, 2));
    }
  }
}

async function main() {
    // Parse command line arguments first - do this early to ensure debug mode is properly set
    const args = process.argv.slice(2);
    const shouldFillInWeeks = args.includes('--fill-all-weeks');
    const isVerboseMode = args.includes('--verbose');
    
    // Log startup info if in verbose mode
    if (isVerboseMode) {
        console.log('[VERBOSE] Command line args:', JSON.stringify(args));
        console.log('[VERBOSE] Running in verbose mode');
        console.log('[VERBOSE] Fill-in mode enabled:', shouldFillInWeeks);
    }
    
    // Check if required environment variables are set
    if (!config.toggl.apiToken) {
        console.error('Error: TOGGL_API_TOKEN is not set in environment variables');
        process.exit(1);
    }
    
    if (!config.toggl.workspaceId) {
        console.error('Error: TOGGL_WORKSPACE_ID is not set in environment variables');
        process.exit(1);
    }

    // Add additional validation for Confluence credentials
    if (!config.confluence.username) {
        console.error('Error: CONFLUENCE_USERNAME is not set in environment variables');
        process.exit(1);
    }
    
    if (!config.confluence.apiToken) {
        console.error('Error: CONFLUENCE_API_TOKEN is not set in environment variables');
        process.exit(1);
    }
    
    if (!config.confluence.baseUrl) {
        console.error('Error: CONFLUENCE_BASE_URL is not set in environment variables');
        process.exit(1);
    }
    
    debugLog('Starting application with config', {
      togglApiUrl: config.toggl.apiUrl,
      togglWorkspaceId: config.toggl.workspaceId,
      confluenceBaseUrl: config.confluence.baseUrl,
      confluenceSpaceKey: config.confluence.spaceKey,
      confluencePageId: config.confluence.pageId,
      confluenceDisplayName: config.confluence.displayName
    });

    const togglService = new TogglService(config.toggl.apiToken || '');
    const confluenceService = new ConfluenceService(
        config.confluence.baseUrl || '',
        config.confluence.apiToken || '',
        config.confluence.spaceKey || '',
        config.confluence.pageId || '',
        config.confluence.username || 'Andres',
        config.confluence.displayName
    );

    try {
        if (shouldFillInWeeks) {
            console.log('Fill-in mode activated. Will attempt to add reports for all missing weeks in the current year.');
            await fillInMissingWeeks(togglService, confluenceService);
        } else {
            // Regular mode - just process the most recent week
            console.log('Processing the most recent week...');
            await processWeek(togglService, confluenceService, getLastWeekDates());
        }
        
        console.log('All operations completed successfully!');
    } catch (error) {
        console.error('Error:', error instanceof Error ? error.message : error);
        if (config.app.debug) {
            console.error('Full error details:', error);
        }
        process.exit(1);
    }
}

async function fillInMissingWeeks(togglService: TogglService, confluenceService: ConfluenceService) {
    // Get all weeks in the current year
    const allWeeks = getAllWeeksInYear();
    console.log(`Found ${allWeeks.length} weeks in the current year to process.`);
    
    // Get the existing content to check which weeks are already reported
    const existingContent = await confluenceService.getExistingContent();
    
    // Fetch project map once at the beginning
    const projectMap = await togglService.fetchProjects();
    debugLog('Project map', projectMap);
    
    let processedCount = 0;
    let skippedCount = 0;
    let errorCount = 0;
    let noDataCount = 0;
    
    // Process each week in reverse order (newest first)
    // This ensures we discover the earliest allowed date first
    const reversedWeeks = [...allWeeks].reverse();
    
    for (let i = 0; i < reversedWeeks.length; i++) {
        const week = reversedWeeks[i];
        const weekEndDateStr = week.endDate.toLocaleDateString('en-GB', { 
            day: '2-digit', 
            month: '2-digit'
        });
        
        const weekIndex = allWeeks.length - i;
        console.log(`[${weekIndex}/${allWeeks.length}] Week ending ${weekEndDateStr}`);
        
        // Check if this week already exists for this user
        if (confluenceService.hasWeekForUser(existingContent, weekEndDateStr)) {
            if (config.app.debug) console.log(`Checking week ending ${weekEndDateStr}...`);
            console.log(`✓ Already exists. Skipping.`);
            skippedCount++;
            continue;
        }
        
        if (config.app.debug) console.log(`Processing week ending ${weekEndDateStr}...`);
        try {
            // Pass projectMap to processWeek
            await processWeek(togglService, confluenceService, week, projectMap);
            processedCount++;
            // Add a delay to avoid API rate limits
            if (i < reversedWeeks.length - 1) {
                if (config.app.debug) console.log(`Waiting before processing next week...`);
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        } catch (error) {
            if (error instanceof Error && error.message.includes("No time records found")) {
                console.log(`ℹ No time entries found for this week. Skipping.`);
                noDataCount++;
            } else {
                console.error(`✗ Error: ${error instanceof Error ? error.message : String(error)}`);
                errorCount++;
            }
            // Continue with the next week even if this one fails
        }
    }
    
    console.log(`\n===== Summary =====`);
    console.log(`Total weeks found: ${allWeeks.length}`);
    console.log(`Weeks successfully processed: ${processedCount}`);
    console.log(`Weeks skipped (already existed): ${skippedCount}`);
    console.log(`Weeks with no time data: ${noDataCount}`);
    console.log(`Weeks with errors: ${errorCount}`);
}

async function processWeek(
    togglService: TogglService, 
    confluenceService: ConfluenceService, 
    dateRange: { startDate: Date, endDate: Date },
    existingProjectMap?: ProjectMap
) {
    const weekDateStr = dateRange.endDate.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' });
    if (config.app.debug) console.log(`Fetching time records for week ending ${weekDateStr}...`);
    
    debugLog('Date range', { startDate: dateRange.startDate, endDate: dateRange.endDate });
    
    // Only fetch project map if not provided
    const projectMap = existingProjectMap || await togglService.fetchProjects();
    if (!existingProjectMap) {
        debugLog('Project map', projectMap);
    }
    
    const timeRecords = await togglService.fetchTimeRecords(dateRange.startDate, dateRange.endDate);
    console.log(`Retrieved ${timeRecords.length} time entries`);
    
    if (timeRecords.length === 0) {
        throw new Error("No time records found for this period");
    }
    
    // Show only 1 time record as a sample instead of 3
    debugLog('Sample time record', timeRecords.length > 0 ? timeRecords.slice(0, 1) : []);
    
    const formattedReport = formatTimeRecords(timeRecords, projectMap);
    
    if (config.app.debug) console.log(`Posting report for week ending ${weekDateStr} to Confluence...`);
    await confluenceService.postReport(formattedReport, dateRange);
}

main();