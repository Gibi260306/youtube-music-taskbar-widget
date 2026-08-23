/*
    SPDX-FileCopyrightText: 2026 Gibi
    SPDX-License-Identifier: GPL-3.0-or-later
*/

import QtQuick
import QtQuick.Layouts

import org.kde.kirigami 2 as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras 2.0 as PlasmaExtras
import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.private.mpris as Mpris

PlasmoidItem {
    id: root

    switchWidth: Kirigami.Units.gridUnit * 14
    switchHeight: Kirigami.Units.gridUnit * 10

    readonly property var player: mprisModel.currentPlayer
    readonly property bool hasPlayer: player !== null && player !== undefined
    readonly property string track: player?.track ?? ""
    readonly property string artist: player?.artist ?? ""
    readonly property string album: player?.album ?? ""
    readonly property string albumArt: player?.artUrl ?? ""
    readonly property string identity: player?.identity ?? ""
    readonly property int playbackStatus: player?.playbackStatus ?? Mpris.PlaybackStatus.Stopped
    readonly property bool isPlaying: playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool canControl: player?.canControl ?? false
    readonly property bool canPlay: player?.canPlay ?? false
    readonly property bool canPause: player?.canPause ?? false
    readonly property bool canGoPrevious: player?.canGoPrevious ?? false
    readonly property bool canGoNext: player?.canGoNext ?? false
    readonly property bool canSeek: player?.canSeek ?? false
    readonly property bool canRaise: player?.canRaise ?? false
    readonly property double position: player?.position ?? 0
    readonly property double length: player?.length ?? 0
    readonly property real volume: player?.volume ?? 0

    Plasmoid.icon: isPlaying ? "media-playback-playing" : "applications-multimedia"
    Plasmoid.status: hasPlayer ? PlasmaCore.Types.ActiveStatus : PlasmaCore.Types.PassiveStatus

    toolTipMainText: track.length > 0 ? track : "No media playing"
    toolTipSubText: artist.length > 0
        ? artist + (identity.length > 0 ? " — " + identity : "")
        : identity
    toolTipTextFormat: Text.PlainText

    compactRepresentation: Component {
        MouseArea {
            id: compact

            readonly property real artworkSize: Math.max(
                Kirigami.Units.iconSizes.smallMedium,
                Math.min(height - Kirigami.Units.smallSpacing * 2, Kirigami.Units.iconSizes.medium)
            )
            readonly property real desiredTextWidth: Math.min(
                Kirigami.Units.gridUnit * 13,
                Math.max(
                    1,
                    compactTitle.implicitWidth,
                    compactArtist.visible ? compactArtist.implicitWidth : 0
                )
            )
            readonly property real horizontalPadding: Math.max(2, Kirigami.Units.smallSpacing / 2)
            readonly property real compactSpacing: 6
            readonly property real controlsWidth: playPauseButton.visible ? playPauseButton.implicitWidth : 0
            readonly property real visibleSpacing: compactSpacing * (playPauseButton.visible ? 2 : 1)
            readonly property real contentWidth: artworkSize + desiredTextWidth + controlsWidth
                + visibleSpacing + horizontalPadding * 2

            Layout.minimumWidth: contentWidth
            Layout.preferredWidth: contentWidth
            Layout.maximumWidth: Kirigami.Units.gridUnit * 20
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2.25

            implicitWidth: Layout.preferredWidth
            implicitHeight: Layout.preferredHeight
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.BackButton | Qt.ForwardButton

            onClicked: mouse => {
                if (mouse.button === Qt.MiddleButton) {
                    root.togglePlayback();
                } else if (mouse.button === Qt.BackButton) {
                    root.previous();
                } else if (mouse.button === Qt.ForwardButton) {
                    root.next();
                } else {
                    root.expanded = !root.expanded;
                }
            }

            property int accumulatedWheelDelta: 0
            onWheel: wheel => {
                if (!root.hasPlayer) {
                    return;
                }
                accumulatedWheelDelta += (wheel.inverted ? -1 : 1)
                    * (wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : -wheel.angleDelta.x);
                while (accumulatedWheelDelta >= 120) {
                    accumulatedWheelDelta -= 120;
                    root.changeVolume(0.03);
                }
                while (accumulatedWheelDelta <= -120) {
                    accumulatedWheelDelta += 120;
                    root.changeVolume(-0.03);
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: Kirigami.Units.smallSpacing
                color: Kirigami.Theme.highlightColor
                opacity: compact.containsMouse ? 0.14 : 0

                Behavior on opacity {
                    NumberAnimation { duration: Kirigami.Units.shortDuration }
                }
            }

            RowLayout {
                id: compactRow

                anchors.fill: parent
                anchors.leftMargin: compact.horizontalPadding
                anchors.rightMargin: compact.horizontalPadding
                spacing: compact.compactSpacing

                Rectangle {
                    id: compactArtworkFrame

                    Layout.preferredWidth: compact.artworkSize
                    Layout.preferredHeight: Layout.preferredWidth
                    Layout.alignment: Qt.AlignVCenter
                    radius: Kirigami.Units.smallSpacing
                    color: Kirigami.Theme.alternateBackgroundColor
                    clip: true

                    Image {
                        id: compactArtwork

                        anchors.fill: parent
                        source: root.albumArt
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: parent.width * 0.62
                        height: width
                        source: "applications-multimedia"
                        visible: compactArtwork.status !== Image.Ready
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: false
                    Layout.fillHeight: true
                    Layout.minimumWidth: compact.desiredTextWidth
                    Layout.preferredWidth: compact.desiredTextWidth
                    Layout.maximumWidth: compact.desiredTextWidth
                    spacing: 0

                    Item {
                        id: titleViewport

                        Layout.fillWidth: true
                        Layout.preferredHeight: compactTitle.implicitHeight
                        Layout.alignment: Qt.AlignVCenter
                        clip: true

                        PlasmaComponents.Label {
                            id: compactTitle

                            x: 0
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.track.length > 0 ? root.track : "No media playing"
                            font.weight: Font.DemiBold
                            color: Kirigami.Theme.textColor
                            textFormat: Text.PlainText
                            wrapMode: Text.NoWrap
                        }

                        SequentialAnimation {
                            id: titleMarquee

                            running: compactTitle.implicitWidth > titleViewport.width && root.track.length > 0
                            loops: Animation.Infinite

                            PauseAnimation { duration: 1200 }
                            NumberAnimation {
                                target: compactTitle
                                property: "x"
                                from: 0
                                to: Math.min(0, titleViewport.width - compactTitle.implicitWidth - Kirigami.Units.largeSpacing)
                                duration: Math.max(1500, Math.abs(to) * 30)
                                easing.type: Easing.InOutQuad
                            }
                            PauseAnimation { duration: 900 }
                            NumberAnimation {
                                target: compactTitle
                                property: "x"
                                to: 0
                                duration: Math.max(900, Math.abs(compactTitle.x) * 18)
                                easing.type: Easing.InOutQuad
                            }

                            onRunningChanged: {
                                if (!running) {
                                    compactTitle.x = 0;
                                }
                            }
                        }
                    }

                    PlasmaComponents.Label {
                        id: compactArtist

                        Layout.fillWidth: true
                        visible: compact.height >= Kirigami.Units.gridUnit * 2
                        text: root.artist.length > 0 ? root.artist : root.identity
                        color: Kirigami.Theme.disabledTextColor
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                    }
                }

                PlasmaComponents.ToolButton {
                    id: playPauseButton

                    Layout.alignment: Qt.AlignVCenter
                    visible: root.hasPlayer
                    enabled: root.canControl && (root.isPlaying ? root.canPause : root.canPlay)
                    text: root.isPlaying ? "Pause" : "Play"
                    display: PlasmaComponents.AbstractButton.IconOnly
                    icon.name: root.isPlaying ? "media-playback-pause" : "media-playback-start"
                    onClicked: root.togglePlayback()

                    PlasmaComponents.ToolTip {
                        text: parent.text
                    }
                }
            }
        }
    }

    fullRepresentation: Component {
        PlasmaExtras.Representation {
            id: popup

            readonly property real naturalHeight: popupContent.implicitHeight
                + Kirigami.Units.largeSpacing * 2

            Layout.minimumWidth: Kirigami.Units.gridUnit * 18
            Layout.minimumHeight: Math.max(Kirigami.Units.gridUnit * 12, naturalHeight)
            Layout.preferredWidth: Kirigami.Units.gridUnit * 22
            Layout.preferredHeight: Layout.minimumHeight
            Layout.maximumHeight: Layout.preferredHeight

            collapseMarginsHint: true

            ColumnLayout {
                id: popupContent

                anchors.fill: parent
                anchors.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Layout.maximumHeight: implicitHeight
                    Layout.alignment: Qt.AlignTop
                    spacing: Kirigami.Units.largeSpacing

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 7
                        Layout.preferredHeight: Layout.preferredWidth
                        radius: Kirigami.Units.smallSpacing * 1.5
                        color: Kirigami.Theme.alternateBackgroundColor
                        clip: true

                        Image {
                            id: popupArtwork

                            anchors.fill: parent
                            source: root.albumArt
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }

                        Kirigami.Icon {
                            anchors.centerIn: parent
                            width: parent.width * 0.5
                            height: width
                            source: "applications-multimedia"
                            visible: popupArtwork.status !== Image.Ready
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        spacing: Kirigami.Units.smallSpacing

                        PlasmaExtras.Heading {
                            Layout.fillWidth: true
                            level: 2
                            text: root.track.length > 0 ? root.track : "Nothing playing"
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            maximumLineCount: 2
                            wrapMode: Text.Wrap
                        }

                        PlasmaComponents.Label {
                            Layout.fillWidth: true
                            text: root.artist.length > 0 ? root.artist : "Start Pear or play media in your browser"
                            color: Kirigami.Theme.disabledTextColor
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            maximumLineCount: 2
                            wrapMode: Text.Wrap
                        }

                        PlasmaComponents.Label {
                            Layout.fillWidth: true
                            visible: root.album.length > 0
                            text: root.album
                            color: Kirigami.Theme.disabledTextColor
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        PlasmaComponents.Button {
                            visible: root.canRaise
                            text: root.identity.length > 0 ? "Open " + root.identity : "Open player"
                            icon.name: "window"
                            onClicked: root.raisePlayer()
                        }
                    }
                }

                PlasmaComponents.Slider {
                    id: seekSlider

                    Layout.fillWidth: true
                    Layout.maximumHeight: implicitHeight
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    from: 0
                    to: Math.max(1, root.length)
                    value: 0
                    enabled: root.hasPlayer && root.canSeek && root.length > 0
                    onMoved: root.seek(value)

                    Binding {
                        target: seekSlider
                        property: "value"
                        value: root.position
                        when: !seekSlider.pressed
                        restoreMode: Binding.RestoreNone
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.maximumHeight: implicitHeight

                    PlasmaComponents.Label {
                        text: root.formatTime(seekSlider.pressed ? seekSlider.value : root.position)
                        color: Kirigami.Theme.disabledTextColor
                        font.family: "monospace"
                    }

                    Item { Layout.fillWidth: true }

                    PlasmaComponents.Label {
                        text: root.formatTime(root.length)
                        color: Kirigami.Theme.disabledTextColor
                        font.family: "monospace"
                    }
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumHeight: implicitHeight
                    spacing: Kirigami.Units.largeSpacing

                    PlasmaComponents.ToolButton {
                        implicitWidth: Kirigami.Units.gridUnit * 3
                        implicitHeight: implicitWidth
                        enabled: root.canGoPrevious
                        text: "Previous"
                        display: PlasmaComponents.AbstractButton.IconOnly
                        icon.name: "media-skip-backward"
                        onClicked: root.previous()

                        PlasmaComponents.ToolTip { text: parent.text }
                    }

                    PlasmaComponents.ToolButton {
                        implicitWidth: Kirigami.Units.gridUnit * 4
                        implicitHeight: implicitWidth
                        enabled: root.canControl && (root.isPlaying ? root.canPause : root.canPlay)
                        text: root.isPlaying ? "Pause" : "Play"
                        display: PlasmaComponents.AbstractButton.IconOnly
                        icon.name: root.isPlaying ? "media-playback-pause" : "media-playback-start"
                        onClicked: root.togglePlayback()

                        PlasmaComponents.ToolTip { text: parent.text }
                    }

                    PlasmaComponents.ToolButton {
                        implicitWidth: Kirigami.Units.gridUnit * 3
                        implicitHeight: implicitWidth
                        enabled: root.canGoNext
                        text: "Next"
                        display: PlasmaComponents.AbstractButton.IconOnly
                        icon.name: "media-skip-forward"
                        onClicked: root.next()

                        PlasmaComponents.ToolTip { text: parent.text }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.maximumHeight: implicitHeight
                    spacing: Kirigami.Units.smallSpacing

                    Kirigami.Icon {
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: Layout.preferredWidth
                        source: root.volume <= 0.001 ? "audio-volume-muted" : "audio-volume-high"
                    }

                    PlasmaComponents.Slider {
                        id: volumeSlider

                        Layout.fillWidth: true
                        from: 0
                        to: 1
                        stepSize: 0.01
                        value: root.volume
                        enabled: root.hasPlayer && root.canControl
                        onMoved: root.setVolume(value)
                    }

                    PlasmaComponents.Label {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 2.5
                        horizontalAlignment: Text.AlignRight
                        text: Math.round(root.volume * 100) + "%"
                        color: Kirigami.Theme.disabledTextColor
                    }
                }

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    Layout.maximumHeight: implicitHeight
                    horizontalAlignment: Text.AlignHCenter
                    text: root.identity.length > 0 ? root.identity : "MPRIS media controller"
                    color: Kirigami.Theme.disabledTextColor
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                }

                Item {
                    Layout.fillHeight: true
                    Layout.minimumHeight: 0
                }
            }
        }
    }

    function togglePlayback() {
        if (hasPlayer && canControl && (isPlaying ? canPause : canPlay)) {
            player.PlayPause();
        }
    }

    function previous() {
        if (hasPlayer && canGoPrevious) {
            player.Previous();
        }
    }

    function next() {
        if (hasPlayer && canGoNext) {
            player.Next();
        }
    }

    function seek(microseconds) {
        if (hasPlayer && canSeek) {
            player.position = Math.max(0, Math.min(length, microseconds));
        }
    }

    function changeVolume(delta) {
        if (hasPlayer && canControl) {
            player.changeVolume(delta, false);
        }
    }

    function setVolume(newVolume) {
        if (hasPlayer && canControl) {
            const clamped = Math.max(0, Math.min(1, newVolume));
            player.changeVolume(clamped - volume, false);
        }
    }

    function raisePlayer() {
        if (hasPlayer && canRaise) {
            player.Raise();
        }
    }

    function formatTime(microseconds) {
        if (!Number.isFinite(microseconds) || microseconds <= 0) {
            return "0:00";
        }

        const totalSeconds = Math.floor(microseconds / 1000000);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        const paddedSeconds = seconds < 10 ? "0" + seconds : seconds.toString();

        if (hours > 0) {
            const paddedMinutes = minutes < 10 ? "0" + minutes : minutes.toString();
            return hours + ":" + paddedMinutes + ":" + paddedSeconds;
        }
        return minutes + ":" + paddedSeconds;
    }

    onExpandedChanged: {
        if (expanded && hasPlayer) {
            player.updatePosition();
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.expanded && root.isPlaying && root.hasPlayer
        onTriggered: root.player?.updatePosition()
    }

    Mpris.Mpris2Model {
        id: mprisModel
    }
}
