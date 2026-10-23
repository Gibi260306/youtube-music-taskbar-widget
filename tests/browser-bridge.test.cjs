// SPDX-License-Identifier: GPL-3.0-or-later
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = name => fs.readFileSync(path.join(__dirname, '../browser-bridge/extension', name), 'utf8');

function page(initialVolume = 75, origin = 'https://music.youtube.com', transform = value => value) {
    const model = {volume: transform(initialVolume), muted: false, position: 10, status: 1, calls: []};
    const api = {
        getVolume: () => model.volume,
        setVolume: value => { model.volume = value; model.calls.push(value); },
        isMuted: () => model.muted,
        mute: () => { model.muted = true; },
        unMute: () => { model.muted = false; },
        getCurrentTime: () => model.position,
        getDuration: () => 200,
        getPlayerState: () => model.status,
        getVideoData: () => ({video_id: 'abc-123', title: 'Song', author: 'Artist'}),
        playVideo: () => { model.status = 1; },
        pauseVideo: () => { model.status = 2; },
        seekTo: position => { model.position = position; }
    };
    const playerBar = {updateVolume: value => api.setVolume(transform(value))};
    const elements = {'ytmusic-player': {playerApi: api}, '#movie_player': api,
        'ytmusic-player-bar': playerBar};
    for (const name of ['#volume-slider', '#expand-volume-slider']) {
        elements[name] = {
            value: initialVolume,
            visible: name === '#volume-slider',
            getClientRects() { return this.visible ? [{}] : []; },
            getAttribute(name) { return name === 'value' ? String(this.value) : null; },
            dispatchEvent(event) {
                assert.equal(event.type, 'change');
                assert.equal(event.bubbles, true);
                playerBar.updateVolume(this.value);
            }
        };
    }
    const video = {};
    Object.defineProperty(video, 'volume', {set() { throw new Error('Must not write media-element gain'); }});
    elements.video = video;
    const context = vm.createContext({
        location: {origin}, navigator: {mediaSession: {metadata: {title: 'Track', artist: 'Artist'}}},
        document: {querySelector: selector => elements[selector]},
        Event: class { constructor(type, options) { this.type = type; Object.assign(this, options); } }
    });
    vm.runInContext(source('player.js'), context);
    return {model, elements, context, run: (command, value) => context.youtubeMusicCommand(command, value)};
}

test('volume follows the site controls and updates both sliders, including mute/unmute', () => {
    const tab = page();
    assert.equal(tab.run('snapshot').volume, 0.75);
    assert.equal(tab.run('volume', 0.5).volume, 0.5);
    assert.equal(tab.elements['#volume-slider'].value, 50);
    assert.equal(tab.elements['#expand-volume-slider'].value, 50);
    assert.equal(tab.run('volume', 0).muted, true);
    assert.equal(tab.run('volume', 0.2).muted, false);
    assert.equal(tab.model.volume, 20);
    tab.elements['#volume-slider'].value = 35;
    tab.elements['#volume-slider'].dispatchEvent({type: 'change', bubbles: true});
    assert.equal(tab.run('snapshot').volume, 0.35);
});

test('clamps volume, rejects nonfinite requests, and refuses other origins or missing APIs', () => {
    const tab = page();
    assert.equal(tab.run('volume', 4).volume, 1);
    assert.equal(tab.run('volume', -2).volume, 0);
    assert.throws(() => tab.run('volume', NaN), /Invalid volume/);
    assert.equal(page(75, 'https://www.youtube.com').run('volume', 0.2).available, false);
    delete tab.elements['ytmusic-player'];
    delete tab.elements['#movie_player'];
    assert.equal(tab.run('snapshot').available, false);
});

test('playback and seeking use the same selected site player', () => {
    const tab = page();
    assert.equal(tab.run('toggle').playbackStatus, 'Paused');
    assert.equal(tab.run('play').playbackStatus, 'Playing');
    assert.equal(tab.run('seek', 500).position, 200);
    assert.throws(() => tab.run('arbitrary-script'), /Unsupported/);
});

test('site slider 75% is reported as 75% when the internal player gain is 43%', () => {
    // Simulate transformed player gain; never guess or invert the site's curve.
    const tab = page(75, 'https://music.youtube.com', value => Math.round(value * 0.57));
    assert.equal(tab.model.volume, 43);
    assert.equal(tab.run('snapshot').volume, 0.75);
    assert.equal(tab.run('volume', 0.5).volume, 0.5);
    assert.equal(tab.model.volume, Math.round(50 * 0.57));
    assert.equal(tab.elements['#volume-slider'].value, 50);
    tab.elements['#volume-slider'].value = 75;
    tab.elements['#volume-slider'].dispatchEvent({type: 'change', bubbles: true});
    assert.equal(tab.model.volume, 43);
    assert.equal(tab.run('snapshot').volume, 0.75);
});

test('reads the visible compact slider instead of a stale hidden desktop slider', () => {
    const tab = page(75, 'https://music.youtube.com', value => Math.round(value * 0.57));
    tab.elements['#volume-slider'].visible = false;
    tab.elements['#volume-slider'].value = 25;
    tab.elements['#expand-volume-slider'].visible = true;
    assert.equal(tab.run('snapshot').volume, 0.75);
    tab.elements['#expand-volume-slider'].visible = false;
    assert.equal(tab.run('snapshot').volume, 0.75);
    assert.equal(tab.run('volume', 0.5).volume, 0.5);
    assert.equal(tab.elements['#volume-slider'].value, 50);
    assert.equal(tab.elements['#expand-volume-slider'].value, 50);
});

test('falls back to a consistent player-API scale when the site sliders are unavailable', () => {
    const tab = page(75, 'https://music.youtube.com', value => Math.round(value * 0.57));
    delete tab.elements['#volume-slider'];
    delete tab.elements['#expand-volume-slider'];
    assert.equal(tab.run('snapshot').volume, 0.43);
    assert.equal(tab.run('volume', 0.5).volume, 0.5);
    assert.equal(tab.model.volume, 50);
});

test('reads a live drag and acknowledges the site slider rounding without writing during polls', () => {
    const tab = page(43);
    const slider = tab.elements['#volume-slider'];
    slider.dragging = true;
    slider.immediateValue = 75;
    assert.equal(tab.run('snapshot').volume, 0.75);
    assert.deepEqual(tab.model.calls, []);
    slider.dragging = false;
    let percent = 75;
    Object.defineProperty(slider, 'value', {
        get: () => percent,
        set: value => { percent = Math.round(value / 5) * 5; }
    });
    assert.equal(tab.run('volume', 0.43).volume, 0.45);
    assert.equal(tab.model.volume, 45);
});

function background(transform) {
    const pages = new Map([[1, page(75, 'https://music.youtube.com', transform)], [2, page(90, 'https://www.youtube.com')], [3, page(20)]]);
    const tabs = new Map([
        [1, {id: 1, windowId: 10, audible: true, lastAccessed: 1, url: 'https://music.youtube.com/watch?v=abc'}],
        [2, {id: 2, windowId: 10, audible: true, lastAccessed: 100, url: 'https://www.youtube.com/watch?v=other'}],
        [3, {id: 3, windowId: 10, audible: false, lastAccessed: 5, url: 'https://music.youtube.com/watch?v=def'}]
    ]);
    const event = () => ({addListener(callback) { this.callback = callback; }});
    const port = {onMessage: event(), onDisconnect: event(), states: [], postMessage(message) { this.states.push(message); }};
    const context = vm.createContext({console, setInterval() {}, browser: {
        runtime: {connectNative: () => port},
        action: {onClicked: event(), setBadgeText() {}, setTitle() {}},
        alarms: {onAlarm: event(), create() {}},
        windows: {async update() {}},
        tabs: {
            onRemoved: event(), onUpdated: event(),
            async query() { return [...tabs.values()].filter(t => t.url.startsWith('https://music.youtube.com/')); },
            async get(id) { if (!tabs.has(id)) throw new Error('Tab closed'); return tabs.get(id); },
            async update(id) { return tabs.get(id); }
        },
        scripting: {async executeScript({target, func, args}) {
            // Recreate the function as Firefox does: it cannot capture extension globals.
            const tab = pages.get(target.tabId);
            tab.context.args = args;
            return [{result: vm.runInContext('(' + func.toString() + ')(...args)', tab.context)}];
        }}
    }});
    vm.runInContext(source('player.js') + '\n' + source('background.js'), context);
    return {tabs, pages, port, context,
        drain: () => vm.runInContext('queue', context),
        poll: async () => { vm.runInContext('schedulePoll()', context); await vm.runInContext('queue', context); },
        command: message => port.onMessage.callback({type: 'command', command: 'volume', tabId: 1, ...message})};
}

test('pins Music tab; unrelated tab playback and newer Music tabs cannot steal the slider', async () => {
    const bridge = background();
    await bridge.drain();
    assert.equal(bridge.port.states.at(-1).state.tabId, 1);
    bridge.command({value: 0.5});
    await bridge.drain();
    assert.equal(bridge.pages.get(1).model.volume, 50);
    assert.equal(bridge.pages.get(2).model.volume, 90);
    assert.equal(bridge.pages.get(3).model.volume, 20);
    bridge.tabs.get(3).audible = true;
    bridge.tabs.get(3).lastAccessed = 999;
    await bridge.poll();
    assert.equal(bridge.port.states.at(-1).state.tabId, 1);
});

test('rapid slider commands coalesce to the last value and closed-tab commands never retarget', async () => {
    const bridge = background();
    await bridge.drain();
    for (const value of [0.1, 0.4, 0.6]) bridge.command({value});
    await bridge.drain();
    assert.equal(bridge.pages.get(1).model.volume, 60);
    assert.equal(bridge.pages.get(1).model.calls.includes(10), false);
    bridge.tabs.delete(1);
    await bridge.poll();
    bridge.command({value: 0.9}); // Old request for tab 1 after tab 3 takes over.
    await bridge.drain();
    assert.equal(bridge.pages.get(3).model.volume, 20);
});

test('navigation away from Music disables the connection before any page code runs', async () => {
    const bridge = background();
    await bridge.drain();
    bridge.tabs.get(1).url = 'https://example.com/';
    bridge.command({value: 0.1});
    await bridge.drain();
    assert.equal(bridge.port.states.at(-1).state.available, false);
    assert.equal(bridge.pages.get(1).model.volume, 75);
});

test('polling sends manual site slider changes on the UI scale to the native bridge', async () => {
    const bridge = background(value => Math.round(value * 0.57));
    await bridge.drain();
    bridge.command({value: 0.5});
    await bridge.drain();
    assert.equal(bridge.port.states.at(-1).state.volume, 0.5);
    const tab = bridge.pages.get(1);
    tab.elements['#volume-slider'].value = 75;
    tab.elements['#volume-slider'].dispatchEvent({type: 'change', bubbles: true});
    await bridge.poll();
    assert.equal(bridge.port.states.at(-1).state.volume, 0.75);
    assert.equal(tab.model.volume, 43);
});
