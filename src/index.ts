import dotenv from 'dotenv';
import path from 'path';

// Load environment variables before importing anything else
dotenv.config({ path: path.resolve(__dirname, '../.env') });

import { TogglService } from './services/togglService';
import { ConfluenceService } from './services/confluenceService';
import { getAllWeeksInYear, getLastWeekDates } from './utils/dateUtils';
import { formatTimeRecords } from './utils/formatUtils';
import { config } from './config/config';
import { ProjectMap } from './types';
import { debug, info, error } from './utils/logUtils';

async function main() {
    // Parse command line arguments first
    const args = process.argv.slice(2);
    const shouldFillInWeeks = args.includes('--fill-all-weeks');
    const isVerboseMode = args.includes('--verbose');
    
    if (isVerboseMode) {
        info(`[VERBOSE] Command line args: ${JSON.stringify(args)}`);
        info('[VERBOSE] Running in verbose mode');
        info(`[VERBOSE] Fill-in mode enabled: ${shouldFillInWeeks}`);
    }
    
    // Validate required environment variables
    const requiredEnvVars = [
        { value: config.toggl.apiToken, name: 'TOGGL_API_TOKEN' },
        { value: config.toggl.workspaceId, name: 'TOGGL_WORKSPACE_ID' },
        { value: config.confluence.username, name: 'CONFLUENCE_USERNAME' },
        { value: config.confluence.apiToken, name: 'CONFLUENCE_API_TOKEN' },
        { value: config.confluence.baseUrl, name: 'CONFLUENCE_BASE_URL' }
    ];
    
    for (const envVar of requiredEnvVars) {
        if (!envVar.value) {
            error(`${envVar.name} is not set in environment variables`);
            process.exit(1);
        }
    }

    debug('Starting application with config', {
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
            info('Fill-in mode activated. Will attempt to add reports for all missing weeks in the current year.');
            await fillInMissingWeeks(togglService, confluenceService);
        } else {
            // Regular mode - just process the most recent week
            info('Processing the most recent week...');
            await processWeek(togglService, confluenceService, getLastWeekDates());
        }
        
        info('All operations completed successfully!');
    } catch (err) {
        error('Error:', err instanceof Error ? err.message : err);
        if (config.app.debug) {
            error('Full error details:', err);
        }
        process.exit(1);
    }
}

async function fillInMissingWeeks(togglService: TogglService, confluenceService: ConfluenceService) {
    // Get all weeks in the current year
    const allWeeks = getAllWeeksInYear();
    info(`Found ${allWeeks.length} weeks in the current year to process.`);
    
    // Get the existing content to check which weeks are already reported
    const existingContent = await confluenceService.getExistingContent();
    
    // Fetch project map once at the beginning
    const projectMap = await togglService.fetchProjects();
    debug('Project map', projectMap);
    
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
        info(`[${weekIndex}/${allWeeks.length}] Week ending ${weekEndDateStr}`);
        
        // Check if this week already exists for this user
        if (confluenceService.hasWeekForUser(existingContent, weekEndDateStr)) {
            debug(`Checking week ending ${weekEndDateStr}...`);
            info(`✓ Already exists. Skipping.`);
            skippedCount++;
            continue;
        }
        
        debug(`Processing week ending ${weekEndDateStr}...`);
        try {
            // Pass projectMap to processWeek
            await processWeek(togglService, confluenceService, week, projectMap);
            processedCount++;
            // Add a delay to avoid API rate limits
            if (i < reversedWeeks.length - 1) {
                debug(`Waiting before processing next week...`);
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        } catch (err) {
            if (err instanceof Error && err.message.includes("No time records found")) {
                info(`ℹ No time entries found for this week. Skipping.`);
                noDataCount++;
            } else {
                error(`✗ Error: ${err instanceof Error ? err.message : String(err)}`);
                errorCount++;
            }
            // Continue with the next week even if this one fails
        }
    }
    
    info(`\n===== Summary =====`);
    info(`Total weeks found: ${allWeeks.length}`);
    info(`Weeks successfully processed: ${processedCount}`);
    info(`Weeks skipped (already existed): ${skippedCount}`);
    info(`Weeks with no time data: ${noDataCount}`);
    info(`Weeks with errors: ${errorCount}`);
}

async function processWeek(
    togglService: TogglService, 
    confluenceService: ConfluenceService, 
    dateRange: { startDate: Date, endDate: Date },
    existingProjectMap?: ProjectMap
) {
    const weekDateStr = dateRange.endDate.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' });
    debug(`Fetching time records for week ending ${weekDateStr}...`);
    
    debug('Date range', { startDate: dateRange.startDate, endDate: dateRange.endDate });
    
    // Only fetch project map if not provided
    const projectMap = existingProjectMap || await togglService.fetchProjects();
    if (!existingProjectMap) {
        debug('Project map', projectMap);
    }
    
    const timeRecords = await togglService.fetchTimeRecords(dateRange.startDate, dateRange.endDate);
    info(`Retrieved ${timeRecords.length} time entries`);
    
    if (timeRecords.length === 0) {
        throw new Error("No time records found for this period");
    }
    
    // Show only 1 time record as a sample instead of 3
    debug('Sample time record', timeRecords.length > 0 ? timeRecords.slice(0, 1) : []);
    
    const formattedReport = formatTimeRecords(timeRecords, projectMap);
    
    debug(`Posting report for week ending ${weekDateStr} to Confluence...`);
    await confluenceService.postReport(formattedReport, dateRange);
}

main();