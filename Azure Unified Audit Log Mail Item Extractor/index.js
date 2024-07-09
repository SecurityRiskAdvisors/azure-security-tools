"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// Load secret parameters from environment variables
// @ts-ignore
const endpointCribl = process.env.endpointCribl;
// @ts-ignore
const tenantId = process.env.tenantId;
// @ts-ignore
const clientId = process.env.clientId;
// @ts-ignore
const clientSecret = process.env.clientSecret;
// These helpers express minutes and seconds in milliseconds.
const seconds = (seconds) => seconds * 1000;
const minutes = (minutes) => seconds(minutes * 60);
/**
 * Create a Query Window
 * @param duration Length of the Query Window in Milliseconds
 * @param lag Amount of time to delay windows by, to allow results to fully populate. Milliseconds.
 * @returns a query window, with start and end expressed in milliseconds.
 */
const getQueryWindow = (duration, lag = 0) => {
    const now = Date.now();
    const timeSinceClamp = now % duration;
    const clamped = now - timeSinceClamp;
    const end = clamped - lag;
    const start = end - duration;
    return { start, end };
};
// Get a bearer token
async function getToken() {
    console.log(`[gettoken] Getting bearer token from O365 Management API...`);
    const tokenUrl = `https://login.microsoftonline.com/${tenantId}/oauth2/token`;
    const tokenSettings = {
        grant_type: "client_credentials",
        client_id: `${clientId}`,
        client_secret: `${clientSecret}`,
        resource: "https://manage.office.com",
    };
    const requestBody = new URLSearchParams(Object.entries(tokenSettings));
    const responseStream = await fetch(tokenUrl, {
        method: 'POST',
        headers: {
            'content-type': 'application/x-www-form-urlencoded',
        },
        body: requestBody,
    });
    const tokenResponse = await responseStream.json();
    const token = tokenResponse.access_token;
    console.log(`[gettoken] Bearer token received!`);
    return token;
}
async function listBlobs(token, start, end) {
    const baseUrl = `https://manage.office.com/api/v1.0/${tenantId}/activity/feed/`;
    const startTime = new Date(start).toISOString();
    const endTime = new Date(end).toISOString();
    console.log(`[listblobs] Fetching list of storage blobs from ${startTime} to ${endTime}`);
    const endpoint = `${baseUrl}/subscriptions/content?contentType=Audit.Exchange&startTime=${startTime}&endTime=${endTime}`;
    const responseStream = await fetch(endpoint, {
        headers: {
            'authorization': `Bearer ${token}`
        }
    });
    const blobs = await responseStream.json();
    const blobUris = blobs.map((blob) => blob.contentUri);
    console.log(`[listblobs] Fetched list of ${blobUris.length} storage blobs`);
    return blobUris;
}
async function getBlob(token, blobUri) {
    const responseStream = await fetch(blobUri, {
        headers: {
            'authorization': `Bearer ${token}`
        }
    });
    const blobUriResponse = await responseStream.json();
    return blobUriResponse;
}
async function postBlob(blob) {
    await fetch(endpointCribl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(blob),
    });
}
async function processBlob(token, blobUri) {
    console.log(`Downloading ${blobUri}`);
    const blob = await getBlob(token, blobUri);
    console.log(`Uploading ${blobUri}`);
    await postBlob(blob);
    console.log(`Finished uploading ${blobUri}`);
}
async function main() {
    console.log(`[main] Starting!`);
    const { start, end } = getQueryWindow(minutes(5), minutes(5));
    const token = await getToken();
    const blobUris = await listBlobs(token, start, end);
    // Transform each URI into a "process" (Promise)
    const processes = blobUris.map(blobUri => processBlob(token, blobUri));
    // Wait for all of the processes to complete
    // Use allSettled, instead of all, so we don't short-circuit on a single blob failure
    await Promise.allSettled(processes);
    console.log(`[main] Done!`);
}
// @ts-ignore
module.exports = main;
