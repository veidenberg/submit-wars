import { config } from '../config/config';

export function debug(message: string, data?: any): void {
  if (config.app.debug) {
    console.log(`[DEBUG] ${message}`);
    if (data !== undefined) {
      console.log(JSON.stringify(data, null, 2));
    }
  }
}

export function info(message: string): void {
  console.log(message);
}

export function warn(message: string): void {
  console.warn(`[WARNING] ${message}`);
}

export function error(message: string, err?: any): void {
  console.error(`[ERROR] ${message}`);
  if (err && config.app.debug) {
    console.error(err);
  }
}
