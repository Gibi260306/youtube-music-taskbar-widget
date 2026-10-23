// SPDX-License-Identifier: GPL-3.0-or-later
/* global youtubeMusicCommand */
const HOST = "com.gibi.youtube_music";
let port = null;
let selectedTabId = null;
let queue = Promise.resolve();
let pollQueued = false;
let pendingVolume = null;
let volumeQueued = false;

function enqueue(operation) {
    queue = queue.then(operation).catch(error => {
        console.warn("YouTube Music companion:", error.message);
        sendState({available: false});
    });
    return queue;
}

function sendState(state) {
    if (port) port.postMessage({type: "state", state});
}

async function readTab(tabId, command = "snapshot", value = null) {
    const tab = await browser.tabs.get(tabId);
    if (!tab.url?.startsWith("https://music.youtube.com/")) return {available: false};
    const results = await browser.scripting.executeScript({
        target: {tabId}, world: "MAIN", func: youtubeMusicCommand, args: [command, value]
    });
    return {...(results[0]?.result || {available: false}), tabId};
}

async function poll() {
    const tabs = await browser.tabs.query({url: "https://music.youtube.com/*"});
    // Keep a chosen Music tab pinned: playing media in another tab must not
    // redirect a pending slider command to it.
    let tab = tabs.find(candidate => candidate.id === selectedTabId);
    if (!tab) {
        tabs.sort((a, b) => Number(b.audible) - Number(a.audible)
            || (b.lastAccessed || 0) - (a.lastAccessed || 0));
        tab = tabs[0];
        selectedTabId = tab?.id ?? null;
    }
    sendState(tab ? await readTab(tab.id) : {available: false});
}

function schedulePoll() {
    if (pollQueued || !port) return;
    pollQueued = true;
    enqueue(async () => {
        try { await poll(); }
        finally { pollQueued = false; }
    });
}

async function runCommand(message) {
    // A command for a closed/replaced tab is dropped, never retargeted.
    if (!Number.isInteger(message.tabId) || message.tabId !== selectedTabId) return;
    if (message.command === "raise") {
        const tab = await browser.tabs.get(message.tabId);
        if (!tab.url?.startsWith("https://music.youtube.com/")) return;
        await browser.tabs.update(tab.id, {active: true});
        await browser.windows.update(tab.windowId, {focused: true});
    } else {
        sendState(await readTab(message.tabId, message.command, message.value));
    }
}

function receiveCommand(message) {
    if (message?.type !== "command") return;
    if (message.command !== "volume") {
        enqueue(() => runCommand(message));
        return;
    }
    // Dragging a slider can generate many requests. Apply the newest value,
    // rather than letting old values keep playing back after the drag stops.
    pendingVolume = message;
    if (volumeQueued) return;
    volumeQueued = true;
    enqueue(async () => {
        try {
            while (pendingVolume) {
                const latest = pendingVolume;
                pendingVolume = null;
                await runCommand(latest);
            }
        } finally { volumeQueued = false; }
    });
}

function connect() {
    if (port) return;
    const connection = browser.runtime.connectNative(HOST);
    port = connection;
    connection.onMessage.addListener(receiveCommand);
    connection.onDisconnect.addListener(() => {
        if (port === connection) port = null;
        pendingVolume = null;
        browser.action.setBadgeText({text: "!"});
        browser.action.setTitle({title: "YouTube Music: install the local bridge, then click to reconnect"});
    });
    browser.action.setBadgeText({text: ""});
    browser.action.setTitle({title: "Reconnect YouTube Music Taskbar"});
    schedulePoll();
}

browser.alarms.onAlarm.addListener(alarm => {
    if (alarm.name === "reconnect") { connect(); schedulePoll(); }
});
browser.alarms.create("reconnect", {periodInMinutes: 1});
browser.action.onClicked.addListener(() => { connect(); schedulePoll(); });
browser.tabs.onRemoved.addListener(schedulePoll);
browser.tabs.onUpdated.addListener((_id, change) => {
    if (change.status === "complete" || change.url) schedulePoll();
});
setInterval(schedulePoll, 1000);
connect();
