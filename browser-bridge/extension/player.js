// SPDX-License-Identifier: GPL-3.0-or-later

// This function is serialized by executeScript and runs in the page's MAIN
// world. Keep it self-contained; never pass extension APIs into that world.
function youtubeMusicCommand(command = "snapshot", value = null) {
    if (location.origin !== "https://music.youtube.com") {
        return {available: false};
    }
    const api = [document.querySelector("ytmusic-player")?.playerApi,
        document.querySelector("#movie_player")].find(candidate =>
        typeof candidate?.getVolume === "function" && typeof candidate?.setVolume === "function");
    if (!api || !Number.isFinite(api.getVolume())) {
        return {available: false};
    }
    const playerBar = document.querySelector("ytmusic-player-bar");
    const sliders = ["#volume-slider", "#expand-volume-slider"]
        .map(selector => document.querySelector(selector)).filter(Boolean);
    const sliderPercent = slider => {
        let value = slider?.dragging ? slider.immediateValue : slider?.value;
        if (value === undefined || value === null || value === "") {
            value = slider?.getAttribute?.("value");
        }
        if (value === null || value === undefined || typeof value === "boolean"
            || (typeof value === "string" && value.trim() === "")) return null;
        const percent = Number(value);
        return Number.isFinite(percent) && percent >= 0 && percent <= 100 ? percent : null;
    };
    const visible = slider => {
        if (!(slider.getClientRects?.().length > 0)) return false;
        const style = typeof getComputedStyle === "function" ? getComputedStyle(slider) : null;
        return style?.visibility !== "hidden" && style?.display !== "none";
    };
    const readableSliders = sliders.filter(slider => sliderPercent(slider) !== null);
    // A compact volume popover can close between polls. Keep reading the last
    // visible control instead of reverting to a stale hidden desktop slider.
    const sourceKey = Symbol.for("com.gibi.youtube_music.volume_slider");
    const previousSlider = globalThis[sourceKey];
    const slider = readableSliders.find(visible)
        || (readableSliders.includes(previousSlider) ? previousSlider : readableSliders[0]);
    if (slider) globalThis[sourceKey] = slider;
    const next = document.querySelector("ytmusic-player-bar .next-button");
    const previous = document.querySelector("ytmusic-player-bar .previous-button");
    const usable = button => !!button && !button.disabled && !button.hasAttribute("disabled")
        && button.getAttribute("aria-disabled") !== "true";
    if (command === "volume") {
        if (!Number.isFinite(value)) throw new Error("Invalid volume");
        let percent = Math.round(Math.max(0, Math.min(1, value)) * 100);
        if (slider) {
            slider.value = percent;
            percent = sliderPercent(slider) ?? percent;
        }
        // The player bar applies YouTube Music's gain curve. Its slider value
        // and api.getVolume() are different scales, so read and write the bar
        // scale together; do not invert or hard-code the site's curve.
        if (slider && typeof playerBar?.updateVolume === "function") {
            playerBar.updateVolume(percent);
        } else {
            api.setVolume(percent);
            slider?.dispatchEvent(new Event("change", {bubbles: true, composed: true}));
        }
        if (percent > 0) api.unMute?.();
        else api.mute?.();
        for (const peer of sliders) {
            peer.value = percent;
        }
    } else if (command === "toggle") {
        if (api.getPlayerState?.() === 1) api.pauseVideo?.();
        else api.playVideo?.();
    } else if (command === "play") {
        api.playVideo?.();
    } else if (command === "pause") {
        api.pauseVideo?.();
    } else if (command === "next" && usable(next)) {
        next.click();
    } else if (command === "previous" && usable(previous)) {
        previous.click();
    } else if (command === "seek") {
        if (!Number.isFinite(value)) throw new Error("Invalid position");
        api.seekTo?.(Math.max(0, Math.min(api.getDuration?.() || 0, value)), true);
    } else if (command !== "snapshot") {
        throw new Error("Unsupported player command");
    }
    const metadata = navigator.mediaSession?.metadata;
    const video = api.getVideoData?.() || {};
    const id = String(video.video_id || "");
    const number = v => Number.isFinite(v) ? Math.max(0, v) : 0;
    return {
        available: true,
        volume: (sliderPercent(slider) ?? Math.max(0, Math.min(100, api.getVolume()))) / 100,
        muted: api.isMuted?.() === true,
        title: metadata?.title || video.title || "YouTube Music",
        artist: metadata?.artist || video.author || "",
        album: metadata?.album || "",
        artUrl: metadata?.artwork?.slice(-1)[0]?.src || "",
        url: /^[\w-]+$/.test(id) ? "https://music.youtube.com/watch?v=" + id : location.origin,
        duration: number(api.getDuration?.()),
        position: number(api.getCurrentTime?.()),
        playbackStatus: api.getPlayerState?.() === 1 ? "Playing" : "Paused",
        canPlay: typeof api.playVideo === "function",
        canPause: typeof api.pauseVideo === "function",
        canSeek: typeof api.seekTo === "function" && number(api.getDuration?.()) > 0,
        canGoNext: usable(next),
        canGoPrevious: usable(previous),
        seeked: command === "seek"
    };
}
